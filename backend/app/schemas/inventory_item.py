from pydantic import BaseModel, ConfigDict


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
    unit_cost: float
    unit_price: float
    quantity_on_hand: float = 0.0
    reorder_threshold: float = 0.0
    supplier_id: str | None = None


class InventoryItemUpdate(BaseModel):
    sku: str | None = None
    name: str | None = None
    category: str | None = None
    unit_cost: float | None = None
    unit_price: float | None = None
    reorder_threshold: float | None = None
    supplier_id: str | None = None


class InventoryItemListResponse(BaseModel):
    items: list[InventoryItemRead]
    total: int
    page: int
    page_size: int
