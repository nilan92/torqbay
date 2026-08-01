import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.tenant import Tenant
from app.models.user import User, UserRole


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_user_belongs_to_a_tenant_and_has_a_role():
    session = _session()
    tenant = Tenant(name="Colombo Auto Repair")
    session.add(tenant)
    session.commit()

    user = User(
        tenant_id=tenant.id,
        name="Nimal Perera",
        email="nimal@colomboauto.lk",
        password_hash="hashed",
        role=UserRole.owner,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    assert user.tenant_id == tenant.id
    assert user.role == UserRole.owner
    assert user.is_active is True


def test_user_email_is_globally_unique():
    session = _session()
    tenant = Tenant(name="Colombo Auto Repair")
    session.add(tenant)
    session.commit()

    session.add(
        User(
            tenant_id=tenant.id,
            name="Nimal Perera",
            email="dupe@colomboauto.lk",
            password_hash="hashed",
            role=UserRole.owner,
        )
    )
    session.commit()

    session.add(
        User(
            tenant_id=tenant.id,
            name="Second Person",
            email="dupe@colomboauto.lk",
            password_hash="hashed",
            role=UserRole.manager,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
