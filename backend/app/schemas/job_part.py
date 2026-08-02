from pydantic import BaseModel, ConfigDict, Field


class JobPartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    job_id: str
    inventory_item_id: str
    quantity: float
    unit_cost_at_time: float
    unit_price_at_time: float
    overdrawn: bool
    shortfall: float


class JobPartCreate(BaseModel):
    inventory_item_id: str
    quantity: float = Field(gt=0)


class JobPartListResponse(BaseModel):
    items: list[JobPartRead]
    total: int
    page: int
    page_size: int
