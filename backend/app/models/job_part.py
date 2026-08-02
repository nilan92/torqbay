from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class JobPart(Base, TenantScopedMixin):
    __tablename__ = "job_parts"

    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    inventory_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    quantity: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    unit_cost_at_time: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    unit_price_at_time: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    overdrawn: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    shortfall: Mapped[float] = mapped_column(
        Float(precision=53), default=0.0, server_default="0", nullable=False
    )
