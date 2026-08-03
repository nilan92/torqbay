from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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
    # Flat labour charge for this job. Sri Lankan workshops bill labour as one
    # amount per job, not hours x rate.
    labor_cost: float | None = Field(default=None, ge=0)


class JobStatusUpdate(BaseModel):
    status: JobStatus


class JobListResponse(BaseModel):
    items: list[JobRead]
    total: int
    page: int
    page_size: int
