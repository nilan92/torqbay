from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.platform_admin import PlatformAdmin
from app.models.tenant import Tenant
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    payload = decode_token(token, audience="tenant_user", token_type="access")
    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user


def require_role(*roles: UserRole):
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this role")
        return user

    return checker


def get_current_admin(
    token: Annotated[str, Depends(admin_oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> PlatformAdmin:
    payload = decode_token(token, audience="platform_admin", token_type="access")
    admin = db.get(PlatformAdmin, payload.get("sub"))
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return admin
