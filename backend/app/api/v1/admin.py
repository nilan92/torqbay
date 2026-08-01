from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.platform_admin import PlatformAdmin
from app.schemas.auth import AccessTokenResponse, LoginRequest

router = APIRouter()


@router.post("/admin/auth/login", response_model=AccessTokenResponse)
def admin_login(payload: LoginRequest, db: Session = Depends(get_db)) -> AccessTokenResponse:
    admin = db.query(PlatformAdmin).filter(PlatformAdmin.email == payload.email).first()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return AccessTokenResponse(access_token=create_access_token(admin.id, "platform_admin"))
