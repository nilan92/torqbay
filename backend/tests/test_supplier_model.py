from app.models.supplier import Supplier
from app.models.tenant import Tenant


def _tenant(db_session):
    tenant = Tenant(name="Colombo Auto Repair")
    db_session.add(tenant)
    db_session.commit()
    return tenant


def test_supplier_persists_with_tenant_scope(db_session):
    tenant = _tenant(db_session)

    supplier = Supplier(tenant_id=tenant.id, name="Lanka Parts Ltd", contact_info="011-2345678")
    db_session.add(supplier)
    db_session.commit()

    stored = db_session.query(Supplier).one()
    assert stored.id is not None
    assert stored.tenant_id == tenant.id
    assert stored.name == "Lanka Parts Ltd"
    assert stored.contact_info == "011-2345678"
    assert stored.created_at is not None
    assert stored.deleted_at is None


def test_supplier_contact_info_is_optional(db_session):
    tenant = _tenant(db_session)

    supplier = Supplier(tenant_id=tenant.id, name="Walk-in Supplier")
    db_session.add(supplier)
    db_session.commit()

    assert db_session.query(Supplier).one().contact_info is None
