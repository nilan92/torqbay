from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.core.dependencies import get_current_user, require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    TechnicianListResponse,
    UserCreate,
    UserListResponse,
    UserRead,
)

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
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        email=payload.email.lower(),
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
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> UserListResponse:
    query = db.query(User).filter(User.tenant_id == current_user.tenant_id)
    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()
    return UserListResponse(items=users, total=total, page=page, page_size=page_size)


@router.get("/technicians", response_model=TechnicianListResponse)
def list_technicians(
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TechnicianListResponse:
    """id + name only, for staff assigning a job or starting a timer.

    Deliberately not GET /users: that endpoint is owner+manager only and
    returns every field including email and role. Frontdesk can assign jobs
    and record labour but couldn't see who to pick.
    """
    technicians = (
        db.query(User)
        .filter(User.tenant_id == current_user.tenant_id, User.role == UserRole.technician)
        .order_by(User.name)
        .all()
    )
    return TechnicianListResponse(items=technicians, total=len(technicians))
