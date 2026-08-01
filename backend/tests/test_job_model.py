from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.asset import Asset
from app.models.customer import Customer
from app.models.job import Job, JobStatus
from app.models.tenant import Tenant


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_job_defaults_to_open_status_with_no_technician_assigned():
    session = _session()
    tenant = Tenant(name="Colombo Auto Repair")
    session.add(tenant)
    session.commit()

    customer = Customer(tenant_id=tenant.id, name="Nimal Perera")
    session.add(customer)
    session.commit()

    asset = Asset(tenant_id=tenant.id, customer_id=customer.id, type="vehicle", label="Toyota Corolla")
    session.add(asset)
    session.commit()

    job = Job(
        tenant_id=tenant.id,
        customer_id=customer.id,
        asset_id=asset.id,
        title="Brake pad replacement",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    assert job.id is not None
    assert job.status == JobStatus.open
    assert job.assigned_technician_id is None
    assert job.started_at is None
    assert job.completed_at is None
    assert job.labor_cost == 0.0
