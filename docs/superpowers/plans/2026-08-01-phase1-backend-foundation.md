# Phase 1 Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the backend project every other Phase 1 sub-plan depends on: FastAPI scaffold, MySQL/SQLAlchemy models for `tenants`/`users`/`platform_admins`, JWT auth (access + refresh, two audiences: tenant users and platform admins), role-based access control, and the tenant-isolation guarantee that every later feature relies on.

**Architecture:** A single FastAPI app (`backend/app`) with a tenant-scoped SQLAlchemy declarative base whose mixin injects `id`/`tenant_id`/timestamps/soft-delete into every tenant-owned model. Two independent JWT audiences (`tenant_user`, `platform_admin`) keep platform-admin auth (used to provision tenants) fully separate from tenant-user auth. `tenant_id` is never read from client input — every scoped query filters by the `tenant_id` on the authenticated user row loaded server-side from the token's `sub` claim.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, MySQL 8 (via PyMySQL) for dev/prod, SQLite in-memory for the automated test suite (fast, no Docker dependency for `pytest`; see Task 1 note), PyJWT, bcrypt, pytest + httpx.

## Global Constraints

- Multi-tenancy is shared-database, row-level isolation — every tenant-owned table has `tenant_id`; it is always derived server-side from the authenticated user's DB row, never trusted from a request body/query param/token claim directly. (Source: [architecture doc](/Users/nilan/Desktop/WorkshopExpo/docs/02-architecture.md))
- Four tenant-scoped roles: `owner`, `manager`, `technician`, `frontdesk`. A separate, non-tenant-scoped `platform admin` provisions tenants. (Source: [overview doc](/Users/nilan/Desktop/WorkshopExpo/docs/01-overview.md))
- Auth is JWT, access + refresh tokens. (Source: [architecture doc](/Users/nilan/Desktop/WorkshopExpo/docs/02-architecture.md))
- Backend module layout: `core/`, `db/`, `models/`, `schemas/`, `api/v1/`. (Source: [architecture doc](/Users/nilan/Desktop/WorkshopExpo/docs/02-architecture.md))
- Every tenant-owned table includes `id`, `tenant_id`, `created_at`, `updated_at`, `deleted_at` unless stated otherwise. (Source: [data model doc](/Users/nilan/Desktop/WorkshopExpo/docs/03-data-model.md))
- This plan's own engineering choice: automated tests run against SQLite in-memory for speed (`Base.metadata.create_all`, bypassing Alembic); MySQL via Docker Compose is for manual dev/migration verification only. Both dialects are simple enough here (strings, booleans, one enum, one FK) that this doesn't risk masking a MySQL-specific bug — revisit if a later sub-plan introduces MySQL-specific column types.

---

## Task 1: Project Scaffold & Config

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/.env.example`
- Create: `backend/pytest.ini`
- Create: `backend/docker-compose.yml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/tests/__init__.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `app.core.config.settings` — a `Settings` instance with attributes `database_url: str`, `jwt_secret: str`, `jwt_access_expire_minutes: int`, `jwt_refresh_expire_days: int`. Every later task reads config through this object.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_config.py
import importlib


def test_settings_have_sane_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    from app.core import config
    importlib.reload(config)

    assert config.settings.database_url.startswith("sqlite") or config.settings.database_url.startswith("mysql")
    assert config.settings.jwt_secret == "test-secret"
    assert config.settings.jwt_access_expire_minutes > 0
    assert config.settings.jwt_refresh_expire_days > 0


def test_settings_read_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://u:p@localhost/db")
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    from app.core import config
    importlib.reload(config)

    assert config.settings.database_url == "mysql+pymysql://u:p@localhost/db"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'` (or `app.core`) since nothing exists yet.

- [ ] **Step 3: Write the scaffold files**

```text
# backend/requirements.txt
fastapi==0.115.6
uvicorn[standard]==0.32.1
sqlalchemy==2.0.36
alembic==1.14.0
pydantic==2.10.3
pydantic-settings==2.6.1
email-validator==2.2.0
pymysql==1.1.1
bcrypt==4.2.1
pyjwt==2.10.1
python-multipart==0.0.19
```

```text
# backend/requirements-dev.txt
-r requirements.txt
pytest==8.3.4
httpx==0.28.1
```

```text
# backend/.env.example
DATABASE_URL=mysql+pymysql://torqbay:devpassword@localhost:3306/torqbay
JWT_SECRET=change-me-to-a-real-secret
JWT_ACCESS_EXPIRE_MINUTES=30
JWT_REFRESH_EXPIRE_DAYS=30
```

```ini
# backend/pytest.ini
[pytest]
pythonpath = .
```

```yaml
# backend/docker-compose.yml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: devroot
      MYSQL_DATABASE: torqbay
      MYSQL_USER: torqbay
      MYSQL_PASSWORD: devpassword
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  mysql_data:
```

```python
# backend/app/__init__.py
```

```python
# backend/app/core/__init__.py
```

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 30


settings = Settings()
```

```python
# backend/tests/__init__.py
```

- [ ] **Step 4: Install dependencies**

Run (from `backend/`, inside a virtualenv): `pip install -r requirements-dev.txt`

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/requirements-dev.txt backend/.env.example backend/pytest.ini backend/docker-compose.yml backend/app/__init__.py backend/app/core/__init__.py backend/app/core/config.py backend/tests/__init__.py backend/tests/test_config.py
git commit -m "feat: add backend project scaffold and settings"
```

---

## Task 2: DB Session, Declarative Base, Timestamp Mixin

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Test: `backend/tests/test_db_base.py`

**Interfaces:**
- Consumes: `app.core.config.settings.database_url`
- Produces: `app.db.base.Base` (SQLAlchemy `DeclarativeBase`), `app.db.base.TimestampMixin` (adds `created_at`, `updated_at`, `deleted_at`), `app.db.session.get_db` (FastAPI dependency yielding a `Session`), `app.db.session.SessionLocal`, `app.db.session.engine`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_db_base.py
from sqlalchemy import create_engine, String
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from app.db.base import Base, TimestampMixin


class _WidgetForTest(Base, TimestampMixin):
    __tablename__ = "widgets_test_only"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))


def test_timestamp_mixin_sets_created_updated_and_leaves_deleted_null():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    widget = _WidgetForTest(name="bolt")
    session.add(widget)
    session.commit()
    session.refresh(widget)

    assert widget.created_at is not None
    assert widget.updated_at is not None
    assert widget.deleted_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_db_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/db/__init__.py
```

```python
# backend/app/db/base.py
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, nullable=True)
```

```python
# backend/app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/__init__.py backend/app/db/base.py backend/app/db/session.py backend/tests/test_db_base.py
git commit -m "feat: add SQLAlchemy base, timestamp mixin, and db session"
```

---

## Task 3: Tenant Model + Alembic Setup

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/tenant.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Test: `backend/tests/test_tenant_model.py`

**Interfaces:**
- Consumes: `app.db.base.Base`, `app.db.base.TimestampMixin`
- Produces: `app.models.tenant.Tenant` — columns `id: str` (UUID4 string PK), `name: str`, `business_registration_number: str | None`, `vat_registration_number: str | None`, `address: str | None`, `phone: str | None`, `email: str | None`, `logo_url: str | None`, `currency: str` (default `"LKR"`), `default_tax_rate: float` (default `0.0`), `is_active: bool` (default `True`).

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_tenant_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/models/__init__.py
```

```python
# backend/app/models/tenant.py
import uuid

from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vat_registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="LKR", server_default="LKR", nullable=False)
    default_tax_rate: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
```

```ini
# backend/alembic.ini
[alembic]
script_location = alembic
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

```python
# backend/alembic/env.py
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base
from app.models import tenant  # noqa: F401 -- registers Tenant on Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

```mako
# backend/alembic/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tenant_model.py -v`
Expected: PASS

- [ ] **Step 5: Generate and apply the migration against the real dev MySQL**

Run (from `backend/`):
```bash
docker compose up -d mysql
cp .env.example .env   # edit JWT_SECRET/DATABASE_URL if needed
alembic revision --autogenerate -m "create tenants table"
alembic upgrade head
```
Expected: a new file under `alembic/versions/` creating the `tenants` table, and `alembic upgrade head` exits 0. This step only proves the migration applies cleanly to MySQL — it is not part of the pytest suite.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/__init__.py backend/app/models/tenant.py backend/alembic.ini backend/alembic/env.py backend/alembic/script.py.mako backend/alembic/versions/ backend/tests/test_tenant_model.py
git commit -m "feat: add Tenant model and Alembic setup"
```

---

## Task 4: TenantScopedMixin + User Model

**Files:**
- Create: `backend/app/models/user.py`
- Modify: `backend/app/db/base.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/test_user_model.py`

**Interfaces:**
- Consumes: `app.models.tenant.Tenant`
- Produces: `app.db.base.TenantScopedMixin` (adds `id`, `tenant_id` FK to `tenants.id`, plus everything `TimestampMixin` adds), `app.models.user.UserRole` (str enum: `owner`, `manager`, `technician`, `frontdesk`), `app.models.user.User` — columns `tenant_id`, `name: str`, `email: str` (globally unique), `phone: str | None`, `password_hash: str`, `role: UserRole`, `is_active: bool`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_user_model.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_user_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.user'`

- [ ] **Step 3: Add `TenantScopedMixin` to `db/base.py`**

```python
# backend/app/db/base.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, nullable=True)


class TenantScopedMixin(TimestampMixin):
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
```

- [ ] **Step 4: Write the `User` model**

```python
# backend/app/models/user.py
import enum

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class UserRole(str, enum.Enum):
    owner = "owner"
    manager = "manager"
    technician = "technician"
    frontdesk = "frontdesk"


class User(Base, TenantScopedMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
```

- [ ] **Step 5: Register the model with Alembic**

```python
# backend/alembic/env.py
# change this line:
from app.models import tenant  # noqa: F401 -- registers Tenant on Base.metadata
# to:
from app.models import tenant, user  # noqa: F401 -- registers models on Base.metadata
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_user_model.py -v`
Expected: PASS

- [ ] **Step 7: Generate and apply the migration against MySQL**

Run (from `backend/`, with `docker compose up -d mysql` already running):
```bash
alembic revision --autogenerate -m "create users table"
alembic upgrade head
```
Expected: exits 0, `users` table created with a foreign key to `tenants`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/db/base.py backend/app/models/user.py backend/alembic/env.py backend/alembic/versions/ backend/tests/test_user_model.py
git commit -m "feat: add TenantScopedMixin and User model"
```

---

## Task 5: Password Hashing

**Files:**
- Create: `backend/app/core/security.py`
- Test: `backend/tests/test_security_password.py`

**Interfaces:**
- Produces: `app.core.security.hash_password(password: str) -> str`, `app.core.security.verify_password(password: str, hashed: str) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_security_password.py
from app.core.security import hash_password, verify_password


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("correct-horse-battery-staple")

    assert hashed != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", hashed)


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct-horse-battery-staple")

    assert not verify_password("wrong-password", hashed)
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_security_password.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.security'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/core/security.py
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_security_password.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security_password.py
git commit -m "feat: add bcrypt password hashing"
```

---

## Task 6: JWT Token Utilities

**Files:**
- Modify: `backend/app/core/security.py`
- Test: `backend/tests/test_security_jwt.py`

**Interfaces:**
- Consumes: `app.core.config.settings.jwt_secret`, `jwt_access_expire_minutes`, `jwt_refresh_expire_days`
- Produces: `app.core.security.create_access_token(subject: str, audience: str) -> str`, `app.core.security.create_refresh_token(subject: str, audience: str) -> str`, `app.core.security.decode_token(token: str) -> dict`. `decode_token` raises `fastapi.HTTPException(401)` on any invalid/expired/malformed token. Later tasks always use `audience="tenant_user"` or `audience="platform_admin"`, and payloads carry `type` (`"access"`/`"refresh"`) — callers must check both `payload["aud"]` and `payload["type"]` themselves; `decode_token` only proves the signature/expiry are valid.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_security_jwt.py
import pytest
from fastapi import HTTPException

from app.core.security import create_access_token, create_refresh_token, decode_token


def test_access_token_roundtrip():
    token = create_access_token("user-123", "tenant_user")

    payload = decode_token(token)

    assert payload["sub"] == "user-123"
    assert payload["aud"] == "tenant_user"
    assert payload["type"] == "access"


def test_refresh_token_roundtrip():
    token = create_refresh_token("user-123", "tenant_user")

    payload = decode_token(token)

    assert payload["type"] == "refresh"


def test_decode_token_rejects_garbage():
    with pytest.raises(HTTPException) as exc_info:
        decode_token("not-a-real-token")

    assert exc_info.value.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_security_jwt.py -v`
Expected: FAIL with `ImportError: cannot import name 'create_access_token'`

- [ ] **Step 3: Add JWT utilities to `security.py`**

```python
# backend/app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import HTTPException, status

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def _create_token(subject: str, audience: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "aud": audience,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_access_token(subject: str, audience: str) -> str:
    return _create_token(subject, audience, "access", timedelta(minutes=settings.jwt_access_expire_minutes))


def create_refresh_token(subject: str, audience: str) -> str:
    return _create_token(subject, audience, "refresh", timedelta(days=settings.jwt_refresh_expire_days))


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_security_jwt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security_jwt.py
git commit -m "feat: add JWT access/refresh token utilities"
```

---

## Task 7: PlatformAdmin Model

**Files:**
- Create: `backend/app/models/platform_admin.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/test_platform_admin_model.py`

**Interfaces:**
- Produces: `app.models.platform_admin.PlatformAdmin` — columns `id: str` (UUID PK), `email: str` (unique), `password_hash: str`, plus `TimestampMixin` fields. Not tenant-scoped — no `tenant_id`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_platform_admin_model.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_platform_admin_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.platform_admin'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/models/platform_admin.py
import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PlatformAdmin(Base, TimestampMixin):
    __tablename__ = "platform_admins"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
```

- [ ] **Step 4: Register the model with Alembic**

```python
# backend/alembic/env.py
# change this line:
from app.models import tenant, user  # noqa: F401 -- registers models on Base.metadata
# to:
from app.models import platform_admin, tenant, user  # noqa: F401 -- registers models on Base.metadata
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_platform_admin_model.py -v`
Expected: PASS

- [ ] **Step 6: Generate and apply the migration against MySQL**

Run (from `backend/`, with `docker compose up -d mysql` already running):
```bash
alembic revision --autogenerate -m "create platform_admins table"
alembic upgrade head
```
Expected: exits 0.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/platform_admin.py backend/alembic/env.py backend/alembic/versions/ backend/tests/test_platform_admin_model.py
git commit -m "feat: add PlatformAdmin model"
```

---

## Task 8: FastAPI App Skeleton + Admin Login

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/v1/__init__.py`
- Create: `backend/app/api/v1/router.py`
- Create: `backend/app/api/v1/admin.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_admin_auth.py`

**Interfaces:**
- Consumes: `app.core.security.verify_password`, `create_access_token`, `app.models.platform_admin.PlatformAdmin`
- Produces: `app.main.app` (the FastAPI instance, mounted at `/api/v1`), `POST /api/v1/admin/auth/login` returning `{"access_token": str, "token_type": "bearer"}`, and shared pytest fixtures `db_session` and `client` (in `conftest.py`) that every subsequent test file uses.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
```

```python
# backend/tests/test_admin_auth.py
def test_admin_login_with_valid_credentials(client, platform_admin):
    response = client.post("/api/v1/admin/auth/login", json=platform_admin)

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_admin_login_with_wrong_password(client, platform_admin):
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": platform_admin["email"], "password": "wrong"},
    )

    assert response.status_code == 401


def test_admin_login_with_unknown_email(client):
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "nobody@torqbay.test", "password": "whatever"},
    )

    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_admin_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write the schemas, router, and app**

```python
# backend/app/schemas/__init__.py
```

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
```

```python
# backend/app/api/__init__.py
```

```python
# backend/app/api/v1/__init__.py
```

```python
# backend/app/api/v1/admin.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.platform_admin import PlatformAdmin
from app.schemas.auth import AccessTokenResponse, LoginRequest

router = APIRouter()


@router.post("/admin/auth/login", response_model=AccessTokenResponse)
def admin_login(payload: LoginRequest, db: Session = Depends(get_db)) -> AccessTokenResponse:
    admin = db.query(PlatformAdmin).filter(PlatformAdmin.email == payload.email).first()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return AccessTokenResponse(access_token=create_access_token(admin.id, "platform_admin"))
```

```python
# backend/app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1 import admin

api_router = APIRouter()
api_router.include_router(admin.router, tags=["admin"])
```

```python
# backend/app/main.py
from fastapi import FastAPI

from app.api.v1.router import api_router

app = FastAPI(title="Torqbay API")
app.include_router(api_router, prefix="/api/v1")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_admin_auth.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/__init__.py backend/app/schemas/auth.py backend/app/api backend/app/main.py backend/tests/conftest.py backend/tests/test_admin_auth.py
git commit -m "feat: add FastAPI app skeleton and platform admin login"
```

---

## Task 9: Provision Tenants (`POST /admin/tenants`)

**Files:**
- Create: `backend/app/core/dependencies.py`
- Create: `backend/app/schemas/tenant.py`
- Create: `backend/app/schemas/user.py`
- Modify: `backend/app/api/v1/admin.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_admin_tenants.py`

**Interfaces:**
- Consumes: `app.core.security.decode_token`, `app.models.platform_admin.PlatformAdmin`
- Produces: `app.core.dependencies.get_current_admin` (FastAPI dependency, resolves the `platform_admin`-audience bearer token to a `PlatformAdmin` row or raises 401), `app.schemas.tenant.TenantCreate` / `TenantRead`, `app.schemas.user.UserRead`, `POST /api/v1/admin/tenants` (requires admin auth, creates a `Tenant` + its `owner` `User` in one request, returns `TenantRead`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_admin_tenants.py
def test_create_tenant_requires_admin_auth(client):
    response = client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Nimal Perera",
            "owner_email": "nimal@colomboauto.lk",
            "owner_password": "ownerpass123",
        },
    )

    assert response.status_code == 401


def test_admin_can_create_tenant_with_owner(client, platform_admin):
    login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    token = login.json()["access_token"]

    response = client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Nimal Perera",
            "owner_email": "nimal@colomboauto.lk",
            "owner_password": "ownerpass123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Colombo Auto Repair"
    assert body["is_active"] is True
    assert body["currency"] == "LKR"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_admin_tenants.py -v`
Expected: FAIL with 404 (route doesn't exist yet) on both tests.

- [ ] **Step 3: Write `get_current_admin`**

```python
# backend/app/core/dependencies.py
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.platform_admin import PlatformAdmin

admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/auth/login")


def get_current_admin(
    token: Annotated[str, Depends(admin_oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> PlatformAdmin:
    payload = decode_token(token)
    if payload.get("type") != "access" or payload.get("aud") != "platform_admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    admin = db.get(PlatformAdmin, payload.get("sub"))
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return admin
```

- [ ] **Step 4: Write the schemas**

```python
# backend/app/schemas/user.py
from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    email: str
    phone: str | None
    role: UserRole
    is_active: bool


class UserCreate(BaseModel):
    name: str
    email: str
    phone: str | None = None
    password: str
    role: UserRole
```

```python
# backend/app/schemas/tenant.py
from pydantic import BaseModel, ConfigDict, EmailStr


class TenantCreate(BaseModel):
    name: str
    owner_name: str
    owner_email: EmailStr
    owner_password: str


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    currency: str
    is_active: bool
```

- [ ] **Step 5: Add the endpoint to `admin.py`**

```python
# backend/app/api/v1/admin.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.platform_admin import PlatformAdmin
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.auth import AccessTokenResponse, LoginRequest
from app.schemas.tenant import TenantCreate, TenantRead

router = APIRouter()


@router.post("/admin/auth/login", response_model=AccessTokenResponse)
def admin_login(payload: LoginRequest, db: Session = Depends(get_db)) -> AccessTokenResponse:
    admin = db.query(PlatformAdmin).filter(PlatformAdmin.email == payload.email).first()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return AccessTokenResponse(access_token=create_access_token(admin.id, "platform_admin"))


@router.post("/admin/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    _admin: Annotated[PlatformAdmin, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Tenant:
    tenant = Tenant(name=payload.name)
    db.add(tenant)
    db.flush()

    owner = User(
        tenant_id=tenant.id,
        name=payload.owner_name,
        email=payload.owner_email,
        password_hash=hash_password(payload.owner_password),
        role=UserRole.owner,
    )
    db.add(owner)
    db.commit()
    db.refresh(tenant)
    return tenant
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_admin_tenants.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/dependencies.py backend/app/schemas/tenant.py backend/app/schemas/user.py backend/app/api/v1/admin.py backend/tests/test_admin_tenants.py
git commit -m "feat: add tenant provisioning endpoint"
```

---

## Task 10: Tenant User Login + `GET /users/me`

**Files:**
- Modify: `backend/app/core/dependencies.py`
- Create: `backend/app/api/v1/auth.py`
- Create: `backend/app/api/v1/users.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_auth_login.py`
- Test: `backend/tests/test_users_me.py`

**Interfaces:**
- Produces: `app.core.dependencies.get_current_user` (resolves a `tenant_user`-audience bearer token to a `User` row or raises 401), `POST /api/v1/auth/login` (returns `TokenResponse` with access + refresh tokens), `GET /api/v1/users/me` (returns `UserRead` for the authenticated user).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_auth_login.py
def _create_tenant_and_owner(client, platform_admin, email="nimal@colomboauto.lk", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Nimal Perera",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return email, password


def test_login_with_valid_credentials_returns_tokens(client, platform_admin):
    email, password = _create_tenant_and_owner(client, platform_admin)

    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_login_with_wrong_password_returns_401(client, platform_admin):
    email, _ = _create_tenant_and_owner(client, platform_admin)

    response = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})

    assert response.status_code == 401
```

```python
# backend/tests/test_users_me.py
def _login(client, platform_admin, email="nimal@colomboauto.lk", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Nimal Perera",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def test_users_me_requires_auth(client):
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401


def test_users_me_returns_current_user(client, platform_admin):
    token = _login(client, platform_admin)

    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "nimal@colomboauto.lk"
    assert body["role"] == "owner"
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `pytest tests/test_auth_login.py tests/test_users_me.py -v`
Expected: FAIL — routes don't exist (404s).

- [ ] **Step 3: Add `get_current_user` to `dependencies.py`**

```python
# backend/app/core/dependencies.py
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.platform_admin import PlatformAdmin
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/admin/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    payload = decode_token(token)
    if payload.get("type") != "access" or payload.get("aud") != "tenant_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user


def get_current_admin(
    token: Annotated[str, Depends(admin_oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> PlatformAdmin:
    payload = decode_token(token)
    if payload.get("type") != "access" or payload.get("aud") != "platform_admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    admin = db.get(PlatformAdmin, payload.get("sub"))
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return admin
```

- [ ] **Step 4: Write `auth.py` and `users.py` routers**

```python
# backend/app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(
        access_token=create_access_token(user.id, "tenant_user"),
        refresh_token=create_refresh_token(user.id, "tenant_user"),
    )
```

```python
# backend/app/api/v1/users.py
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter()


@router.get("/users/me", response_model=UserRead)
def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
```

- [ ] **Step 5: Wire both routers into the app**

```python
# backend/app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1 import admin, auth, users

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(admin.router, tags=["admin"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_auth_login.py tests/test_users_me.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/dependencies.py backend/app/api/v1/auth.py backend/app/api/v1/users.py backend/app/api/v1/router.py backend/tests/test_auth_login.py backend/tests/test_users_me.py
git commit -m "feat: add tenant user login and /users/me"
```

---

## Task 11: Role Enforcement + Tenant Isolation (`POST/GET /users`)

**Files:**
- Modify: `backend/app/core/dependencies.py`
- Modify: `backend/app/api/v1/users.py`
- Test: `backend/tests/test_users_create.py`
- Test: `backend/tests/test_tenant_isolation.py`

This is the task that proves the whole point of the multi-tenant foundation, so it gets the most thorough tests in this plan.

**Interfaces:**
- Produces: `app.core.dependencies.require_role(*roles: UserRole)` (a dependency factory — returns a FastAPI dependency that 403s if `current_user.role` isn't in `roles`), `POST /api/v1/users` (owner/manager only, creates a staff user in the caller's own tenant), `GET /api/v1/users` (owner/manager only, lists users filtered to `tenant_id == current_user.tenant_id` — never any other tenant's rows).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_users_create.py
def _owner_token(client, platform_admin, email="ownerd@example.com", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Tenant D Workshop",
            "owner_name": "Owner",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def test_owner_can_create_staff_user(client, platform_admin):
    token = _owner_token(client, platform_admin)

    response = client.post(
        "/api/v1/users",
        json={
            "name": "Front Desk",
            "email": "frontdesk@example.com",
            "password": "frontpass123",
            "role": "frontdesk",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "frontdesk"
    assert body["email"] == "frontdesk@example.com"


def test_create_user_rejects_duplicate_email(client, platform_admin):
    token = _owner_token(client, platform_admin, email="ownere@example.com")

    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": "duplicate@example.com", "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {token}"},
    )
    response = client.post(
        "/api/v1/users",
        json={
            "name": "Tech Two",
            "email": "duplicate@example.com",
            "password": "techpass123",
            "role": "technician",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
```

```python
# backend/tests/test_tenant_isolation.py
def _create_tenant_owner_and_login(client, platform_admin, tenant_name, email, password):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={"name": tenant_name, "owner_name": "Owner", "owner_email": email, "owner_password": password},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def test_tenant_cannot_see_another_tenants_users(client, platform_admin):
    token_a = _create_tenant_owner_and_login(
        client, platform_admin, "Tenant A Workshop", "ownera@example.com", "passwordA123"
    )
    token_b = _create_tenant_owner_and_login(
        client, platform_admin, "Tenant B Workshop", "ownerb@example.com", "passwordB123"
    )

    response_a = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token_a}"})
    response_b = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token_b}"})

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    emails_visible_to_a = {user["email"] for user in response_a.json()}
    emails_visible_to_b = {user["email"] for user in response_b.json()}

    assert emails_visible_to_a == {"ownera@example.com"}
    assert emails_visible_to_b == {"ownerb@example.com"}


def test_technician_cannot_list_users(client, platform_admin):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Tenant C Workshop",
            "owner_name": "Owner",
            "owner_email": "ownerc@example.com",
            "owner_password": "passwordC123",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    owner_login = client.post(
        "/api/v1/auth/login", json={"email": "ownerc@example.com", "password": "passwordC123"}
    )
    owner_token = owner_login.json()["access_token"]

    client.post(
        "/api/v1/users",
        json={"name": "Tech One", "email": "tech1@example.com", "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    tech_login = client.post("/api/v1/auth/login", json={"email": "tech1@example.com", "password": "techpass123"})
    tech_token = tech_login.json()["access_token"]

    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {tech_token}"})

    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `pytest tests/test_users_create.py tests/test_tenant_isolation.py -v`
Expected: FAIL — `POST /users` and `GET /users` don't exist yet (404s).

- [ ] **Step 3: Add `require_role` to `dependencies.py`**

```python
# backend/app/core/dependencies.py
# add below the existing get_current_user function:
from app.models.user import User, UserRole  # noqa: F811 -- extends existing import


def require_role(*roles: UserRole):
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this role")
        return user

    return checker
```

(Note: merge this import with the existing `from app.models.user import User` line at the top of the file rather than duplicating it — the final file should import `User, UserRole` once.)

- [ ] **Step 4: Add `POST /users` and `GET /users` to `users.py`**

```python
# backend/app/api/v1/users.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserRead

router = APIRouter()


@router.get("/users/me", response_model=UserRead)
def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_user: Annotated[User, Depends(require_role(UserRole.owner, UserRole.manager))],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserRead])
def list_users(
    current_user: Annotated[User, Depends(require_role(UserRole.owner, UserRole.manager))],
    db: Annotated[Session, Depends(get_db)],
) -> list[User]:
    return db.query(User).filter(User.tenant_id == current_user.tenant_id).all()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_users_create.py tests/test_tenant_isolation.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Run the full test suite so far**

Run (from `backend/`): `pytest -v`
Expected: all tests across every task so far pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/dependencies.py backend/app/api/v1/users.py backend/tests/test_users_create.py backend/tests/test_tenant_isolation.py
git commit -m "feat: add role enforcement and prove tenant isolation on /users"
```

---

## Task 12: Refresh Token Endpoint

**Files:**
- Modify: `backend/app/api/v1/auth.py`
- Test: `backend/tests/test_auth_refresh.py`

**Interfaces:**
- Produces: `POST /api/v1/auth/refresh` (accepts `{"refresh_token": str}`, returns `{"access_token": str, "token_type": "bearer"}`; rejects access tokens and any token not audienced/typed as a `tenant_user` refresh token with 401).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_auth_refresh.py
def _create_tenant_and_login(client, platform_admin, email="refresh-owner@example.com", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Refresh Test Workshop",
            "owner_name": "Owner",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()


def test_refresh_returns_new_access_token(client, platform_admin):
    tokens = _create_tenant_and_login(client, platform_admin)

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_refresh_rejects_an_access_token(client, platform_admin):
    tokens = _create_tenant_and_login(client, platform_admin)

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})

    assert response.status_code == 401


def test_refresh_rejects_garbage_token(client):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})

    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `pytest tests/test_auth_refresh.py -v`
Expected: FAIL with 404 (route doesn't exist yet).

- [ ] **Step 3: Add the endpoint**

```python
# backend/app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import AccessTokenResponse, LoginRequest, RefreshRequest, TokenResponse

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(
        access_token=create_access_token(user.id, "tenant_user"),
        refresh_token=create_refresh_token(user.id, "tenant_user"),
    )


@router.post("/auth/refresh", response_model=AccessTokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> AccessTokenResponse:
    claims = decode_token(payload.refresh_token)
    if claims.get("type") != "refresh" or claims.get("aud") != "tenant_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = db.get(User, claims.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return AccessTokenResponse(access_token=create_access_token(user.id, "tenant_user"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_auth_refresh.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run (from `backend/`): `pytest -v`
Expected: every test across all 12 tasks passes.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/auth.py backend/tests/test_auth_refresh.py
git commit -m "feat: add refresh token endpoint"
```

---

## Definition of Done

- `pytest -v` (run from `backend/`) passes with zero failures.
- `docker compose up -d mysql && alembic upgrade head` (run from `backend/`) applies all migrations cleanly against a real MySQL 8 instance.
- Manual smoke test: `POST /api/v1/admin/tenants` (as a platform admin) creates a tenant + owner; that owner can `POST /api/v1/auth/login`, hit `GET /api/v1/users/me`, create a technician via `POST /api/v1/users`, and a second tenant's owner cannot see the first tenant's users via `GET /api/v1/users`.
- This plan does not yet cover: customers/assets/jobs (sub-plan 2), inventory (sub-plan 3), invoicing/payments/payroll (sub-plan 4), reports (sub-plan 5), or any mobile app work (sub-plans 6-7) — those are separate plans per the [roadmap](/Users/nilan/Desktop/WorkshopExpo/docs/08-roadmap.md).
