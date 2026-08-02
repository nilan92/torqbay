import enum

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class InvoiceLineItemType(str, enum.Enum):
    labor = "labor"
    part = "part"
    other = "other"


class InvoiceLineItem(Base, TenantScopedMixin):
    __tablename__ = "invoice_line_items"

    invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("invoices.id"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    line_total: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    type: Mapped[InvoiceLineItemType] = mapped_column(nullable=False)
