from app.models.inventory_item import InventoryItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderStatus
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier import Supplier
from app.models.tenant import Tenant


def _setup(db_session):
    tenant = Tenant(name="Colombo Auto Repair")
    db_session.add(tenant)
    db_session.commit()

    supplier = Supplier(tenant_id=tenant.id, name="Lanka Parts Ltd")
    item = InventoryItem(
        tenant_id=tenant.id, sku="BP-001", name="Brake pad set", unit_cost=2500.0, unit_price=4000.0
    )
    db_session.add_all([supplier, item])
    db_session.commit()
    return tenant, supplier, item


def test_purchase_order_defaults_to_draft(db_session):
    tenant, supplier, _ = _setup(db_session)

    po = PurchaseOrder(tenant_id=tenant.id, supplier_id=supplier.id)
    db_session.add(po)
    db_session.commit()

    stored = db_session.query(PurchaseOrder).one()
    assert stored.status == PurchaseOrderStatus.draft
    assert stored.received_at is None


def test_purchase_order_items_link_to_an_order(db_session):
    tenant, supplier, item = _setup(db_session)
    po = PurchaseOrder(tenant_id=tenant.id, supplier_id=supplier.id)
    db_session.add(po)
    db_session.commit()

    line = PurchaseOrderItem(
        tenant_id=tenant.id,
        purchase_order_id=po.id,
        inventory_item_id=item.id,
        quantity=20.0,
        unit_cost=2400.0,
    )
    db_session.add(line)
    db_session.commit()

    stored = db_session.query(PurchaseOrderItem).one()
    assert stored.purchase_order_id == po.id
    assert stored.quantity == 20.0
    assert stored.unit_cost == 2400.0
