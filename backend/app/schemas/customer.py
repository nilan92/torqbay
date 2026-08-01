from pydantic import BaseModel, ConfigDict


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None


class CustomerCreate(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None


class CustomerListResponse(BaseModel):
    items: list[CustomerRead]
    total: int
    page: int
    page_size: int
