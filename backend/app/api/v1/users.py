from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserListResponse, UserRead

router = APIRouter()


@router.get("/users/me", response_model=UserRead)
def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_user: Annotated[User, Depends(require_role(UserRole.owner))],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=UserListResponse)
def list_users(
    current_user: Annotated[User, Depends(require_role(UserRole.owner, UserRole.manager))],
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 20,
) -> UserListResponse:
    query = db.query(User).filter(User.tenant_id == current_user.tenant_id)
    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()
    return UserListResponse(items=users, total=total, page=page, page_size=page_size)
