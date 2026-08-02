from app.models.asset import Asset
from app.models.customer import Customer
from app.models.inventory_item import InventoryItem
from app.models.job import Job
from app.models.job_part import JobPart
from app.models.tenant import Tenant


def _job_and_item(db_session):
    tenant = Tenant(name="Colombo Auto Repair")
    db_session.add(tenant)
    db_session.commit()

    customer = Customer(tenant_id=tenant.id, name="Nimal Perera")
    db_session.add(customer)
    db_session.commit()

    asset = Asset(tenant_id=tenant.id, customer_id=customer.id, type="vehicle", label="Corolla")
    db_session.add(asset)
    db_session.commit()

    job = Job(tenant_id=tenant.id, customer_id=customer.id, asset_id=asset.id, title="Brake service")
    item = InventoryItem(
        tenant_id=tenant.id, sku="BP-001", name="Brake pad set", unit_cost=2500.0, unit_price=4000.0
    )
    db_session.add_all([job, item])
    db_session.commit()
    return tenant, job, item


def test_job_part_stores_price_snapshots(db_session):
    tenant, job, item = _job_and_item(db_session)

    part = JobPart(
        tenant_id=tenant.id,
        job_id=job.id,
        inventory_item_id=item.id,
        quantity=2.0,
        unit_cost_at_time=2500.0,
        unit_price_at_time=4000.0,
    )
    db_session.add(part)
    db_session.commit()

    stored = db_session.query(JobPart).one()
    assert stored.quantity == 2.0
    assert stored.unit_cost_at_time == 2500.0
    assert stored.unit_price_at_time == 4000.0


def test_job_part_defaults_to_not_overdrawn(db_session):
    tenant, job, item = _job_and_item(db_session)

    part = JobPart(
        tenant_id=tenant.id,
        job_id=job.id,
        inventory_item_id=item.id,
        quantity=1.0,
        unit_cost_at_time=1.0,
        unit_price_at_time=2.0,
    )
    db_session.add(part)
    db_session.commit()

    stored = db_session.query(JobPart).one()
    assert stored.overdrawn is False
    assert stored.shortfall == 0.0
