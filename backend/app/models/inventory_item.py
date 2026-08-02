from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class InventoryItem(Base, TenantScopedMixin):
    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint("tenant_id", "sku", name="uq_inventory_items_tenant_sku"),)

    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_cost: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    quantity_on_hand: Mapped[float] = mapped_column(
        Float(precision=53), default=0.0, server_default="0", nullable=False
    )
    reorder_threshold: Mapped[float] = mapped_column(
        Float(precision=53), default=0.0, server_default="0", nullable=False
    )
    supplier_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("suppliers.id"), nullable=True, index=True
    )
