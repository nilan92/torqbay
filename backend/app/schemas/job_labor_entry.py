from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobLaborEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    technician_id: str
    start_time: datetime
    end_time: datetime | None
    hourly_rate: float


class JobLaborEntryCreate(BaseModel):
    start_time: datetime
    end_time: datetime | None = None
    hourly_rate: float
    technician_id: str


class JobLaborEntryUpdate(BaseModel):
    """Closing a running timer.

    Only `end_time` is settable. `start_time`, `hourly_rate` and
    `technician_id` are recorded when the entry is created and are not
    rewritten — an invoice built from them must stay reproducible.
    """

    end_time: datetime


class JobLaborEntryListResponse(BaseModel):
    items: list[JobLaborEntryRead]
    total: int
    page: int
    page_size: int
