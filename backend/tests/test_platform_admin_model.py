from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.platform_admin import PlatformAdmin


def test_platform_admin_has_no_tenant_id():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    admin = PlatformAdmin(email="admin@torqbay.test", password_hash="hashed")
    session.add(admin)
    session.commit()
    session.refresh(admin)

    assert admin.id is not None
    assert not hasattr(admin, "tenant_id")
