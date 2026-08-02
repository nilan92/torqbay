from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
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


def test_customer_belongs_to_a_tenant():
    session = _session()
    tenant = Tenant(name="Colombo Auto Repair")
    session.add(tenant)
    session.commit()

    customer = Customer(tenant_id=tenant.id, name="Nimal Perera", phone="+94771234567")
    session.add(customer)
    session.commit()
    session.refresh(customer)

    assert customer.id is not None
    assert customer.tenant_id == tenant.id
    assert customer.name == "Nimal Perera"
    assert customer.phone == "+94771234567"
    assert customer.email is None
    assert customer.address is None
    assert customer.notes is None
