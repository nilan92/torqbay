from pydantic import BaseModel, ConfigDict


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    customer_id: str
    type: str
    label: str
    identifier: str | None
    notes: str | None


class AssetCreate(BaseModel):
    type: str
    label: str
    identifier: str | None = None
    notes: str | None = None


class AssetListResponse(BaseModel):
    items: list[AssetRead]
    total: int
    page: int
    page_size: int
