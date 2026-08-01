# backend/tests/test_tenant_model.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.tenant import Tenant


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_tenant_has_expected_defaults():
    session = _session()

    tenant = Tenant(name="Colombo Auto Repair")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    assert tenant.id is not None
    assert tenant.currency == "LKR"
    assert tenant.default_tax_rate == 0.0
    assert tenant.is_active is True
    assert tenant.vat_registration_number is None
