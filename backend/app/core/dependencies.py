from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.platform_admin import PlatformAdmin

admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/auth/login")


def get_current_admin(
    token: Annotated[str, Depends(admin_oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> PlatformAdmin:
    payload = decode_token(token)
    if payload.get("type") != "access" or payload.get("aud") != "platform_admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    admin = db.get(PlatformAdmin, payload.get("sub"))
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return admin
