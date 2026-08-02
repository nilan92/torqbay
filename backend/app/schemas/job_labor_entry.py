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
