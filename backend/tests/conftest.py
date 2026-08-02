import email_validator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ponytail: email-validator rejects the reserved .test TLD by default; our
# fixtures use @torqbay.test emails, so opt into its test-environment mode.
email_validator.TEST_ENVIRONMENT = True

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def platform_admin(db_session):
    from app.core.security import hash_password
    from app.models.platform_admin import PlatformAdmin

    admin = PlatformAdmin(email="admin@torqbay.test", password_hash=hash_password("adminpass123"))
    db_session.add(admin)
    db_session.commit()
    return {"email": "admin@torqbay.test", "password": "adminpass123"}
