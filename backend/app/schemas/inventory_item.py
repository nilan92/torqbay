from pydantic import BaseModel, ConfigDict, Field


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    sku: str
    name: str
    category: str | None
    unit_cost: float
    unit_price: float
    quantity_on_hand: float
    reorder_threshold: float
    supplier_id: str | None


class InventoryItemCreate(BaseModel):
    sku: str
    name: str
    category: str | None = None
    unit_cost: float = Field(ge=0)
    unit_price: float = Field(ge=0)
    quantity_on_hand: float = Field(default=0.0, ge=0)
    reorder_threshold: float = Field(default=0.0, ge=0)
    supplier_id: str | None = None


class InventoryItemUpdate(BaseModel):
    sku: str | None = None
    name: str | None = None
    category: str | None = None
    unit_cost: float | None = Field(default=None, ge=0)
    unit_price: float | None = Field(default=None, ge=0)
    reorder_threshold: float | None = Field(default=None, ge=0)
    supplier_id: str | None = None


class InventoryItemListResponse(BaseModel):
    items: list[InventoryItemRead]
    total: int
    page: int
    page_size: int
