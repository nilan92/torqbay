from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class JobLaborEntry(Base, TenantScopedMixin):
    __tablename__ = "job_labor_entries"

    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    technician_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Optional: technicians here are on monthly salaries, so an hourly rate is
    # neither what the technician earns nor what the customer is charged. Kept
    # for shops that genuinely pay hourly. Customer-facing labour is billed via
    # Job.labor_cost.
    hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
