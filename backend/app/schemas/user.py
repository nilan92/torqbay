from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    email: str
    phone: str | None
    role: UserRole
    is_active: bool


class UserCreate(BaseModel):
    name: str
    email: str
    phone: str | None = None
    password: str
    role: UserRole


class UserListResponse(BaseModel):
    items: list[UserRead]
    total: int
    page: int
    page_size: int
