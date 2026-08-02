import pytest
from sqlalchemy.exc import IntegrityError

from app.models.inventory_item import InventoryItem
from app.models.supplier import Supplier
from app.models.tenant import Tenant


def _tenant(db_session, name="Colombo Auto Repair"):
    tenant = Tenant(name=name)
    db_session.add(tenant)
    db_session.commit()
    return tenant


def test_inventory_item_defaults_quantity_and_threshold_to_zero(db_session):
    tenant = _tenant(db_session)

    item = InventoryItem(
        tenant_id=tenant.id, sku="BP-001", name="Brake pad set", unit_cost=2500.0, unit_price=4000.0
    )
    db_session.add(item)
    db_session.commit()

    stored = db_session.query(InventoryItem).one()
    assert stored.quantity_on_hand == 0.0
    assert stored.reorder_threshold == 0.0
    assert stored.category is None
    assert stored.supplier_id is None


def test_inventory_item_can_link_a_supplier(db_session):
    tenant = _tenant(db_session)
    supplier = Supplier(tenant_id=tenant.id, name="Lanka Parts Ltd")
    db_session.add(supplier)
    db_session.commit()

    item = InventoryItem(
        tenant_id=tenant.id,
        sku="OF-010",
        name="Oil filter",
        category="Filters",
        unit_cost=800.0,
        unit_price=1500.0,
        quantity_on_hand=12.0,
        reorder_threshold=4.0,
        supplier_id=supplier.id,
    )
    db_session.add(item)
    db_session.commit()

    stored = db_session.query(InventoryItem).one()
    assert stored.supplier_id == supplier.id
    assert stored.category == "Filters"
    assert stored.quantity_on_hand == 12.0


def test_sku_is_unique_within_a_tenant(db_session):
    tenant = _tenant(db_session)
    db_session.add(
        InventoryItem(tenant_id=tenant.id, sku="DUP-1", name="First", unit_cost=1.0, unit_price=2.0)
    )
    db_session.commit()

    db_session.add(
        InventoryItem(tenant_id=tenant.id, sku="DUP-1", name="Second", unit_cost=1.0, unit_price=2.0)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_same_sku_is_allowed_in_a_different_tenant(db_session):
    tenant_a = _tenant(db_session, name="Tenant A")
    tenant_b = _tenant(db_session, name="Tenant B")

    db_session.add(
        InventoryItem(tenant_id=tenant_a.id, sku="SHARED-1", name="A", unit_cost=1.0, unit_price=2.0)
    )
    db_session.add(
        InventoryItem(tenant_id=tenant_b.id, sku="SHARED-1", name="B", unit_cost=1.0, unit_price=2.0)
    )
    db_session.commit()

    assert db_session.query(InventoryItem).count() == 2
