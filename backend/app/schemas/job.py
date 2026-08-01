from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job import JobStatus


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    customer_id: str
    asset_id: str
    assigned_technician_id: str | None
    title: str
    description: str | None
    status: JobStatus
    started_at: datetime | None
    completed_at: datetime | None
    labor_cost: float


class JobCreate(BaseModel):
    customer_id: str
    asset_id: str
    title: str
    description: str | None = None
    assigned_technician_id: str | None = None


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assigned_technician_id: str | None = None


class JobStatusUpdate(BaseModel):
    status: JobStatus


class JobListResponse(BaseModel):
    items: list[JobRead]
    total: int
    page: int
    page_size: int
