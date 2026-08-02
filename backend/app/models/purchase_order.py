import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScopedMixin


class PurchaseOrderStatus(str, enum.Enum):
    draft = "draft"
    ordered = "ordered"
    received = "received"


class PurchaseOrder(Base, TenantScopedMixin):
    __tablename__ = "purchase_orders"

    supplier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        default=PurchaseOrderStatus.draft,
        server_default=PurchaseOrderStatus.draft.value,
        nullable=False,
    )
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem", lazy="selectin"
    )
