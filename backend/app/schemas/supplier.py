from pydantic import BaseModel, ConfigDict


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    contact_info: str | None


class SupplierCreate(BaseModel):
    name: str
    contact_info: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact_info: str | None = None


class SupplierListResponse(BaseModel):
    items: list[SupplierRead]
    total: int
    page: int
    page_size: int
