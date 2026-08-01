from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.platform_admin import PlatformAdmin
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.auth import AccessTokenResponse, LoginRequest
from app.schemas.tenant import TenantCreate, TenantRead

router = APIRouter()


@router.post("/admin/auth/login", response_model=AccessTokenResponse)
def admin_login(payload: LoginRequest, db: Session = Depends(get_db)) -> AccessTokenResponse:
    admin = db.query(PlatformAdmin).filter(PlatformAdmin.email == payload.email).first()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return AccessTokenResponse(access_token=create_access_token(admin.id, "platform_admin"))


@router.post("/admin/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    _admin: Annotated[PlatformAdmin, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Tenant:
    existing = db.query(User).filter(User.email == payload.owner_email.lower()).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    tenant = Tenant(name=payload.name)
    db.add(tenant)
    db.flush()

    owner = User(
        tenant_id=tenant.id,
        name=payload.owner_name,
        email=payload.owner_email.lower(),
        password_hash=hash_password(payload.owner_password),
        role=UserRole.owner,
    )
    db.add(owner)
    db.commit()
    db.refresh(tenant)
    return tenant
