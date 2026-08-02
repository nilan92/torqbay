from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.api.v1.inventory_items import INVENTORY_READ_ROLES, _get_item_or_404
from app.api.v1.suppliers import _get_supplier_or_404
from app.core.dependencies import require_role
from app.db.base import _now
from app.db.session import get_db
from app.models.inventory_item import InventoryItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderStatus
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.user import User
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderListResponse,
    PurchaseOrderRead,
    PurchaseOrderStatusUpdate,
)

router = APIRouter()


def _get_po_or_404(db: Session, tenant_id: str, po_id: str) -> PurchaseOrder:
    po = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id)
        .first()
    )
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return po


@router.post("/purchase-orders", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrder:
    _get_supplier_or_404(db, current_user.tenant_id, payload.supplier_id)
    for line in payload.items:
        _get_item_or_404(db, current_user.tenant_id, line.inventory_item_id)

    po = PurchaseOrder(tenant_id=current_user.tenant_id, supplier_id=payload.supplier_id)
    db.add(po)
    db.flush()

    for line in payload.items:
        db.add(
            PurchaseOrderItem(
                tenant_id=current_user.tenant_id,
                purchase_order_id=po.id,
                inventory_item_id=line.inventory_item_id,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
            )
        )

    db.commit()
    db.refresh(po)
    return po


@router.get("/purchase-orders", response_model=PurchaseOrderListResponse)
def list_purchase_orders(
    current_user: Annotated[User, Depends(require_role(*INVENTORY_READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PurchaseOrderListResponse:
    query = db.query(PurchaseOrder).filter(PurchaseOrder.tenant_id == current_user.tenant_id)
    total = query.count()
    orders = query.offset((page - 1) * page_size).limit(page_size).all()
    return PurchaseOrderListResponse(items=orders, total=total, page=page, page_size=page_size)


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderRead)
def get_purchase_order(
    po_id: str,
    current_user: Annotated[User, Depends(require_role(*INVENTORY_READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrder:
    return _get_po_or_404(db, current_user.tenant_id, po_id)


@router.patch("/purchase-orders/{po_id}/receive", response_model=PurchaseOrderRead)
def receive_purchase_order(
    po_id: str,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrder:
    po = _get_po_or_404(db, current_user.tenant_id, po_id)
    if po.status == PurchaseOrderStatus.received:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Purchase order has already been received"
        )

    lines = (
        db.query(PurchaseOrderItem)
        .filter(
            PurchaseOrderItem.purchase_order_id == po.id,
            PurchaseOrderItem.tenant_id == current_user.tenant_id,
        )
        .all()
    )

    for line in lines:
        item = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.id == line.inventory_item_id,
                InventoryItem.tenant_id == current_user.tenant_id,
            )
            .with_for_update()
            .one()
        )
        item.quantity_on_hand = item.quantity_on_hand + line.quantity

    po.status = PurchaseOrderStatus.received
    po.received_at = _now()
    db.commit()
    db.refresh(po)
    return po


_MANUAL_PO_TRANSITIONS: dict[PurchaseOrderStatus, set[PurchaseOrderStatus]] = {
    PurchaseOrderStatus.draft: {PurchaseOrderStatus.ordered},
    PurchaseOrderStatus.ordered: {PurchaseOrderStatus.draft},
    PurchaseOrderStatus.received: set(),
}


@router.patch("/purchase-orders/{po_id}/status", response_model=PurchaseOrderRead)
def update_purchase_order_status(
    po_id: str,
    payload: PurchaseOrderStatusUpdate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrder:
    po = _get_po_or_404(db, current_user.tenant_id, po_id)

    allowed = _MANUAL_PO_TRANSITIONS.get(po.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition purchase order from {po.status.value} to {payload.status.value}",
        )

    po.status = payload.status
    db.commit()
    db.refresh(po)
    return po
