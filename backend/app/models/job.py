import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class JobStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    invoiced = "invoiced"
    paid = "paid"
    cancelled = "cancelled"


class Job(Base, TenantScopedMixin):
    __tablename__ = "jobs"

    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), nullable=False, index=True)
    assigned_technician_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        default=JobStatus.open, server_default=JobStatus.open.value, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Float(precision=53): plain Float is a 4-byte MySQL FLOAT (~7 significant
    # digits) and silently rounds large LKR amounts. The mobile job detail
    # screen writes real labour charges to this column live.
    labor_cost: Mapped[float] = mapped_column(
        Float(precision=53), default=0.0, server_default="0", nullable=False
    )
