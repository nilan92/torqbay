from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class PurchaseOrderItem(Base, TenantScopedMixin):
    __tablename__ = "purchase_order_items"

    purchase_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    inventory_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    quantity: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
