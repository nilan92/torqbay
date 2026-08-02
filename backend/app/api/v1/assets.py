from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES, _get_customer_or_404
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.asset import Asset
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetListResponse, AssetRead

router = APIRouter()


@router.post(
    "/customers/{customer_id}/assets", response_model=AssetRead, status_code=201
)
def create_asset(
    customer_id: str,
    payload: AssetCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Asset:
    _get_customer_or_404(db, current_user.tenant_id, customer_id)
    asset = Asset(tenant_id=current_user.tenant_id, customer_id=customer_id, **payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/customers/{customer_id}/assets", response_model=AssetListResponse)
def list_assets(
    customer_id: str,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> AssetListResponse:
    _get_customer_or_404(db, current_user.tenant_id, customer_id)
    query = db.query(Asset).filter(Asset.customer_id == customer_id, Asset.tenant_id == current_user.tenant_id)
    total = query.count()
    assets = query.offset((page - 1) * page_size).limit(page_size).all()
    return AssetListResponse(items=assets, total=total, page=page, page_size=page_size)
