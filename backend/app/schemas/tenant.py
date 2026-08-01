from pydantic import BaseModel, ConfigDict, EmailStr


class TenantCreate(BaseModel):
    name: str
    owner_name: str
    owner_email: EmailStr
    owner_password: str


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    currency: str
    is_active: bool
