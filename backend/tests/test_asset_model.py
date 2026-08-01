from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.asset import Asset
from app.models.customer import Customer
from app.models.tenant import Tenant


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_asset_belongs_to_a_customer_and_tenant():
    session = _session()
    tenant = Tenant(name="Colombo Auto Repair")
    session.add(tenant)
    session.commit()

    customer = Customer(tenant_id=tenant.id, name="Nimal Perera")
    session.add(customer)
    session.commit()

    asset = Asset(
        tenant_id=tenant.id,
        customer_id=customer.id,
        type="vehicle",
        label="Toyota Corolla 2018",
        identifier="ABC-1234",
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)

    assert asset.id is not None
    assert asset.tenant_id == tenant.id
    assert asset.customer_id == customer.id
    assert asset.type == "vehicle"
    assert asset.label == "Toyota Corolla 2018"
    assert asset.identifier == "ABC-1234"
    assert asset.notes is None
