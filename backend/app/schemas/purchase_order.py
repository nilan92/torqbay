from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.purchase_order import PurchaseOrderStatus


class PurchaseOrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    purchase_order_id: str
    inventory_item_id: str
    quantity: float
    unit_cost: float


class PurchaseOrderItemCreate(BaseModel):
    inventory_item_id: str
    quantity: float = Field(gt=0)
    unit_cost: float = Field(ge=0)


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_id: str
    status: PurchaseOrderStatus
    received_at: datetime | None
    items: list[PurchaseOrderItemRead]


class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderRead]
    total: int
    page: int
    page_size: int


class PurchaseOrderStatusUpdate(BaseModel):
    status: PurchaseOrderStatus
