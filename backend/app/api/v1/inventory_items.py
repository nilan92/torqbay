from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.api.v1.suppliers import _get_supplier_or_404
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.inventory_item import InventoryItem
from app.models.user import User, UserRole
from app.schemas.inventory_item import (
    InventoryItemCreate,
    InventoryItemListResponse,
    InventoryItemRead,
    InventoryItemUpdate,
)

router = APIRouter()

INVENTORY_READ_ROLES = (*STAFF_ROLES, UserRole.technician)


def _get_item_or_404(db: Session, tenant_id: str, item_id: str) -> InventoryItem:
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.id == item_id, InventoryItem.tenant_id == tenant_id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
    return item


def _reject_duplicate_sku(db: Session, tenant_id: str, sku: str, exclude_id: str | None = None) -> None:
    query = db.query(InventoryItem).filter(
        InventoryItem.tenant_id == tenant_id, InventoryItem.sku == sku
    )
    if exclude_id is not None:
        query = query.filter(InventoryItem.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An item with this SKU already exists"
        )


@router.post("/inventory-items", response_model=InventoryItemRead, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    payload: InventoryItemCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> InventoryItem:
    _reject_duplicate_sku(db, current_user.tenant_id, payload.sku)
    if payload.supplier_id is not None:
        _get_supplier_or_404(db, current_user.tenant_id, payload.supplier_id)

    item = InventoryItem(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/inventory-items", response_model=InventoryItemListResponse)
def list_inventory_items(
    current_user: Annotated[User, Depends(require_role(*INVENTORY_READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    low_stock: bool = Query(False),
) -> InventoryItemListResponse:
    query = db.query(InventoryItem).filter(InventoryItem.tenant_id == current_user.tenant_id)
    if low_stock:
        query = query.filter(InventoryItem.quantity_on_hand <= InventoryItem.reorder_threshold)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return InventoryItemListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/inventory-items/{item_id}", response_model=InventoryItemRead)
def get_inventory_item(
    item_id: str,
    current_user: Annotated[User, Depends(require_role(*INVENTORY_READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> InventoryItem:
    return _get_item_or_404(db, current_user.tenant_id, item_id)


@router.patch("/inventory-items/{item_id}", response_model=InventoryItemRead)
def update_inventory_item(
    item_id: str,
    payload: InventoryItemUpdate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> InventoryItem:
    item = _get_item_or_404(db, current_user.tenant_id, item_id)
    updates = payload.model_dump(exclude_unset=True)

    if "sku" in updates:
        _reject_duplicate_sku(db, current_user.tenant_id, updates["sku"], exclude_id=item_id)
    if updates.get("supplier_id") is not None:
        _get_supplier_or_404(db, current_user.tenant_id, updates["supplier_id"])

    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item
