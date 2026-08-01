# Phase 1 Core Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core domain of Torqbay's backend on top of the merged Phase 1 Backend Foundation: customers, assets (the item being repaired), jobs (the core unit of work), job status transitions, and technician labor-time tracking — the workflow a front-desk user and a technician actually live in day to day.

**Architecture:** Straight continuation of the existing FastAPI + SQLAlchemy + `TenantScopedMixin` pattern. Every new table is tenant-scoped and every endpoint derives `tenant_id` from `current_user.tenant_id` (never from client input), exactly as established in the backend foundation. Role enforcement reuses `require_role(*roles)`; jobs add one extra dimension on top of role — a `technician` sees and acts only on jobs assigned to them, enforced by filtering every job query on `assigned_technician_id` when the caller's role is `technician`.

**Tech Stack:** Same as the existing backend — Python 3.11+ (this repo's venv currently runs 3.14 locally / 3.13 in production), FastAPI, SQLAlchemy 2.0, Alembic, MySQL 8 (prod) / SQLite in-memory (tests), PyJWT, bcrypt, pytest + httpx.

## Global Constraints

- Multi-tenancy: `tenant_id` is always derived server-side from `current_user.tenant_id` (or, for the platform-admin path, not applicable here — this plan has no admin endpoints). Never read `tenant_id` from a request body/query param. Every list/detail query filters on it, including lookups by ID (a customer/asset/job ID from another tenant must 404, not leak).
- Role matrix for this plan's endpoints (from `docs/04-api-design.md`): Customers and Assets are full-access for `owner`/`manager`/`frontdesk`, no access for `technician`. Jobs are full-access for `owner`/`manager`/`frontdesk`; `technician` gets a filtered view — sees and acts only on jobs where `assigned_technician_id` equals their own `id`. A technician's job-scoped requests for a job that exists but isn't theirs return 404, not 403 (avoids confirming another job's existence to someone who can't act on it).
- Job status transitions (from `docs/04-api-design.md` and `docs/03-data-model.md`): the full `JobStatus` enum is `open` / `in_progress` / `done` / `invoiced` / `paid` / `cancelled`, but only `open→in_progress`, `open→cancelled`, `in_progress→done`, and `in_progress→cancelled` are reachable through this plan's `PATCH /jobs/{id}/status` endpoint. `invoiced` and `paid` are system-driven transitions owned by the Finance sub-plan (invoice generation, payment recording) — not yet built, and deliberately unreachable manually here.
- `job_parts` (parts consumed by a job, `POST /jobs/{id}/parts`) is explicitly OUT OF SCOPE for this plan — it has a foreign key to `inventory_items`, which doesn't exist until the Inventory sub-plan. Build it there.
- Backend module layout: `core/`, `db/`, `models/`, `schemas/`, `api/v1/` (established).
- Every tenant-owned table: `id`, `tenant_id`, `created_at`, `updated_at`, `deleted_at` via `TenantScopedMixin` (established in `app/db/base.py`).
- Tests run against SQLite in-memory (established convention — fast, no Docker dependency); MySQL migration verification happens manually/via the CI/CD pipeline's `alembic upgrade head` step against the real deploy target, not part of this plan's pytest suite.
- Known, already-tracked deferred item (not this plan's problem to fix): money-ish float fields (`labor_cost`, `hourly_rate`) use `Float` rather than `Decimal`, consistent with the existing `Tenant.default_tax_rate` precedent — flagged in the backend foundation's final review as a followup for whenever the Finance sub-plan does real currency math. Follow the same pattern here, don't fix it in this plan.
- Pagination: list endpoints use `page: int = Query(1, ge=1)`, `page_size: int = Query(20, ge=1, le=100)`, returning `{items, total, page, page_size}` — established in `app/api/v1/users.py`, reuse exactly.

---

## Task 1: Customer Model + Migration

**Files:**
- Create: `backend/app/models/customer.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/test_customer_model.py`

**Interfaces:**
- Consumes: `app.db.base.Base`, `app.db.base.TenantScopedMixin`
- Produces: `app.models.customer.Customer` — columns via `TenantScopedMixin` (`id`, `tenant_id`, `created_at`, `updated_at`, `deleted_at`) plus `name: str`, `phone: str | None`, `email: str | None`, `address: str | None`, `notes: str | None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_customer_model.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/bin/pytest tests/test_customer_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.customer'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/models/customer.py
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class Customer(Base, TenantScopedMixin):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
```

- [ ] **Step 4: Register the model with Alembic**

```python
# backend/alembic/env.py
# change this line:
from app.models import platform_admin, tenant, user  # noqa: F401 -- registers models on Base.metadata
# to:
from app.models import customer, platform_admin, tenant, user  # noqa: F401 -- registers models on Base.metadata
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_customer_model.py -v`
Expected: PASS

- [ ] **Step 6: Generate and apply the migration**

Run (from `backend/`, with `docker compose up -d mysql` if testing against real MySQL locally, otherwise this applies to whatever `DATABASE_URL` resolves to):
```bash
.venv/bin/alembic revision --autogenerate -m "create customers table"
.venv/bin/alembic upgrade head
```
Expected: exits 0, a new file under `alembic/versions/` creating the `customers` table with a foreign key to `tenants`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/customer.py backend/alembic/env.py backend/alembic/versions/ backend/tests/test_customer_model.py
git commit -m "feat: add Customer model"
```

---

## Task 2: Customer Endpoints

**Files:**
- Create: `backend/app/schemas/customer.py`
- Create: `backend/app/api/v1/customers.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_customers_api.py`

**Interfaces:**
- Consumes: `app.core.dependencies.get_current_user`, `app.core.dependencies.require_role`, `app.models.customer.Customer`
- Produces: `app.schemas.customer.CustomerRead` / `CustomerCreate` / `CustomerUpdate` / `CustomerListResponse`. Endpoints: `POST /api/v1/customers`, `GET /api/v1/customers`, `GET /api/v1/customers/{customer_id}`, `PATCH /api/v1/customers/{customer_id}` — all four restricted to `owner`/`manager`/`frontdesk` (403 for `technician`). `app.api.v1.customers._get_customer_or_404(db, tenant_id, customer_id) -> Customer` — later tasks (Task 4's assets endpoints) reuse this exact helper, import it from this module.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_customers_api.py
def _owner_token(client, platform_admin, email="owner-cust@example.com", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Owner",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def _technician_token(client, platform_admin, owner_token, email="tech-cust@example.com"):
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "techpass123"})
    return login.json()["access_token"]


def test_owner_can_create_and_list_customers(client, platform_admin):
    token = _owner_token(client, platform_admin)

    create_response = client.post(
        "/api/v1/customers",
        json={"name": "Nimal Perera", "phone": "+94771234567"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["name"] == "Nimal Perera"
    assert body["phone"] == "+94771234567"

    list_response = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] == 1
    assert list_body["items"][0]["name"] == "Nimal Perera"


def test_technician_cannot_create_customer(client, platform_admin):
    owner_token = _owner_token(client, platform_admin, email="owner-cust2@example.com")
    tech_token = _technician_token(client, platform_admin, owner_token, email="tech-cust2@example.com")

    response = client.post(
        "/api/v1/customers",
        json={"name": "Nimal Perera"},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 403


def test_get_and_update_customer(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-cust3@example.com")
    create_response = client.post(
        "/api/v1/customers",
        json={"name": "Nimal Perera"},
        headers={"Authorization": f"Bearer {token}"},
    )
    customer_id = create_response.json()["id"]

    get_response = client.get(f"/api/v1/customers/{customer_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Nimal Perera"

    update_response = client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"phone": "+94770000000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["phone"] == "+94770000000"
    assert update_response.json()["name"] == "Nimal Perera"


def test_customer_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-cust-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-cust-b@example.com")

    create_response = client.post(
        "/api/v1/customers",
        json={"name": "Tenant A's Customer"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    customer_id = create_response.json()["id"]

    response = client.get(f"/api/v1/customers/{customer_id}", headers={"Authorization": f"Bearer {token_b}"})

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `.venv/bin/pytest tests/test_customers_api.py -v`
Expected: FAIL — routes don't exist (404s where 201/200/403 expected).

- [ ] **Step 3: Write the schemas**

```python
# backend/app/schemas/customer.py
from pydantic import BaseModel, ConfigDict


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None


class CustomerCreate(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None


class CustomerListResponse(BaseModel):
    items: list[CustomerRead]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 4: Write the endpoint**

```python
# backend/app/api/v1/customers.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.customer import Customer
from app.models.user import User, UserRole
from app.schemas.customer import CustomerCreate, CustomerListResponse, CustomerRead, CustomerUpdate

router = APIRouter()

STAFF_ROLES = (UserRole.owner, UserRole.manager, UserRole.frontdesk)


def _get_customer_or_404(db: Session, tenant_id: str, customer_id: str) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    customer = Customer(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/customers", response_model=CustomerListResponse)
def list_customers(
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> CustomerListResponse:
    query = db.query(Customer).filter(Customer.tenant_id == current_user.tenant_id)
    total = query.count()
    customers = query.offset((page - 1) * page_size).limit(page_size).all()
    return CustomerListResponse(items=customers, total=total, page=page, page_size=page_size)


@router.get("/customers/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: str,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    return _get_customer_or_404(db, current_user.tenant_id, customer_id)


@router.patch("/customers/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    customer = _get_customer_or_404(db, current_user.tenant_id, customer_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer
```

- [ ] **Step 5: Wire the router**

```python
# backend/app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1 import admin, auth, customers, users

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(customers.router, tags=["customers"])
api_router.include_router(admin.router, tags=["admin"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_customers_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all tests pass, no regressions.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/customer.py backend/app/api/v1/customers.py backend/app/api/v1/router.py backend/tests/test_customers_api.py
git commit -m "feat: add customer endpoints"
```

---

## Task 3: Asset Model + Migration

**Files:**
- Create: `backend/app/models/asset.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/test_asset_model.py`

**Interfaces:**
- Consumes: `app.db.base.Base`, `app.db.base.TenantScopedMixin`, `app.models.customer.Customer`
- Produces: `app.models.asset.Asset` — `TenantScopedMixin` fields plus `customer_id: str` (FK to `customers.id`), `type: str`, `label: str`, `identifier: str | None`, `notes: str | None`. `type` is a free-text string (e.g. `"vehicle"`, `"electronics"`, `"appliance"`), deliberately not a closed enum — kept generic so it fits any repair vertical, per `docs/03-data-model.md`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_asset_model.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/bin/pytest tests/test_asset_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.asset'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/models/asset.py
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class Asset(Base, TenantScopedMixin):
    __tablename__ = "assets"

    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    identifier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
```

- [ ] **Step 4: Register the model with Alembic**

```python
# backend/alembic/env.py
# change this line:
from app.models import customer, platform_admin, tenant, user  # noqa: F401 -- registers models on Base.metadata
# to:
from app.models import asset, customer, platform_admin, tenant, user  # noqa: F401 -- registers models on Base.metadata
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_asset_model.py -v`
Expected: PASS

- [ ] **Step 6: Generate and apply the migration**

Run (from `backend/`):
```bash
.venv/bin/alembic revision --autogenerate -m "create assets table"
.venv/bin/alembic upgrade head
```
Expected: exits 0.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/asset.py backend/alembic/env.py backend/alembic/versions/ backend/tests/test_asset_model.py
git commit -m "feat: add Asset model"
```

---

## Task 4: Asset Endpoints

**Files:**
- Create: `backend/app/schemas/asset.py`
- Create: `backend/app/api/v1/assets.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_assets_api.py`

**Interfaces:**
- Consumes: `app.api.v1.customers._get_customer_or_404` (Task 2), `app.models.asset.Asset`
- Produces: `app.schemas.asset.AssetRead` / `AssetCreate` / `AssetListResponse`. Endpoints: `POST /api/v1/customers/{customer_id}/assets`, `GET /api/v1/customers/{customer_id}/assets` — both restricted to `owner`/`manager`/`frontdesk`, and both 404 if `customer_id` doesn't belong to the caller's tenant. No `PATCH`/detail-by-id endpoint for assets in this plan — not specified in `docs/04-api-design.md`, don't add it speculatively.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_assets_api.py
def _owner_token(client, platform_admin, email="owner-asset@example.com", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Owner",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def _create_customer(client, token, name="Nimal Perera"):
    response = client.post(
        "/api/v1/customers",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["id"]


def test_owner_can_create_and_list_assets_for_a_customer(client, platform_admin):
    token = _owner_token(client, platform_admin)
    customer_id = _create_customer(client, token)

    create_response = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Toyota Corolla 2018", "identifier": "ABC-1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["customer_id"] == customer_id
    assert body["label"] == "Toyota Corolla 2018"

    list_response = client.get(
        f"/api/v1/customers/{customer_id}/assets", headers={"Authorization": f"Bearer {token}"}
    )
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] == 1
    assert list_body["items"][0]["identifier"] == "ABC-1234"


def test_assets_for_customer_in_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-asset-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-asset-b@example.com")
    customer_id = _create_customer(client, token_a)

    response = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Should not work"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 404


def test_asset_creation_requires_staff_role(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-asset-c@example.com")
    customer_id = _create_customer(client, token)

    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": "tech-asset@example.com", "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {token}"},
    )
    tech_login = client.post(
        "/api/v1/auth/login", json={"email": "tech-asset@example.com", "password": "techpass123"}
    )
    tech_token = tech_login.json()["access_token"]

    response = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Should not work"},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `.venv/bin/pytest tests/test_assets_api.py -v`
Expected: FAIL — routes don't exist.

- [ ] **Step 3: Write the schemas**

```python
# backend/app/schemas/asset.py
from pydantic import BaseModel, ConfigDict


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    customer_id: str
    type: str
    label: str
    identifier: str | None
    notes: str | None


class AssetCreate(BaseModel):
    type: str
    label: str
    identifier: str | None = None
    notes: str | None = None


class AssetListResponse(BaseModel):
    items: list[AssetRead]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 4: Write the endpoint**

```python
# backend/app/api/v1/assets.py
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES, _get_customer_or_404
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.asset import Asset
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetListResponse, AssetRead

router = APIRouter()


@router.post(
    "/customers/{customer_id}/assets", response_model=AssetRead, status_code=201
)
def create_asset(
    customer_id: str,
    payload: AssetCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Asset:
    _get_customer_or_404(db, current_user.tenant_id, customer_id)
    asset = Asset(tenant_id=current_user.tenant_id, customer_id=customer_id, **payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/customers/{customer_id}/assets", response_model=AssetListResponse)
def list_assets(
    customer_id: str,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> AssetListResponse:
    _get_customer_or_404(db, current_user.tenant_id, customer_id)
    query = db.query(Asset).filter(Asset.customer_id == customer_id, Asset.tenant_id == current_user.tenant_id)
    total = query.count()
    assets = query.offset((page - 1) * page_size).limit(page_size).all()
    return AssetListResponse(items=assets, total=total, page=page, page_size=page_size)
```

- [ ] **Step 5: Wire the router**

```python
# backend/app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1 import admin, assets, auth, customers, users

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(customers.router, tags=["customers"])
api_router.include_router(assets.router, tags=["assets"])
api_router.include_router(admin.router, tags=["admin"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_assets_api.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all pass, no regressions.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/asset.py backend/app/api/v1/assets.py backend/app/api/v1/router.py backend/tests/test_assets_api.py
git commit -m "feat: add asset endpoints"
```

---

## Task 5: Job Model + Migration

**Files:**
- Create: `backend/app/models/job.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/test_job_model.py`

**Interfaces:**
- Consumes: `app.db.base.Base`, `app.db.base.TenantScopedMixin`, `app.models.customer.Customer`, `app.models.asset.Asset`, `app.models.user.User`
- Produces: `app.models.job.JobStatus` (str enum: `open`, `in_progress`, `done`, `invoiced`, `paid`, `cancelled`), `app.models.job.Job` — `TenantScopedMixin` fields plus `customer_id: str`, `asset_id: str`, `assigned_technician_id: str | None`, `title: str`, `description: str | None`, `status: JobStatus` (default `open`), `started_at: datetime | None`, `completed_at: datetime | None`, `labor_cost: float` (default `0.0`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_job_model.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/bin/pytest tests/test_job_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.job'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/models/job.py
import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class JobStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    invoiced = "invoiced"
    paid = "paid"
    cancelled = "cancelled"


class Job(Base, TenantScopedMixin):
    __tablename__ = "jobs"

    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), nullable=False, index=True)
    assigned_technician_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        default=JobStatus.open, server_default=JobStatus.open.value, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    labor_cost: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
```

- [ ] **Step 4: Register the model with Alembic**

```python
# backend/alembic/env.py
# change this line:
from app.models import asset, customer, platform_admin, tenant, user  # noqa: F401 -- registers models on Base.metadata
# to:
from app.models import asset, customer, job, platform_admin, tenant, user  # noqa: F401 -- registers models on Base.metadata
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_job_model.py -v`
Expected: PASS

- [ ] **Step 6: Generate and apply the migration**

Run (from `backend/`):
```bash
.venv/bin/alembic revision --autogenerate -m "create jobs table"
.venv/bin/alembic upgrade head
```
Expected: exits 0. Inspect the generated migration file — confirm the `status` column renders as a MySQL-compatible `ENUM('open', 'in_progress', 'done', 'invoiced', 'paid', 'cancelled')`, matching the pattern already used for `users.role`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/job.py backend/alembic/env.py backend/alembic/versions/ backend/tests/test_job_model.py
git commit -m "feat: add Job model with status enum"
```

---

## Task 6: Job Create + List

**Files:**
- Create: `backend/app/schemas/job.py`
- Create: `backend/app/api/v1/jobs.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_jobs_create_list.py`

**Interfaces:**
- Consumes: `app.api.v1.customers.STAFF_ROLES`, `app.models.customer.Customer`, `app.models.asset.Asset`, `app.models.job.Job`, `app.models.job.JobStatus`
- Produces: `app.schemas.job.JobRead` / `JobCreate` / `JobUpdate` / `JobListResponse`. `POST /api/v1/jobs` (staff roles only, validates `customer_id`/`asset_id` belong to the caller's tenant, 404 otherwise). `GET /api/v1/jobs` (any authenticated role; `technician` sees only jobs where `assigned_technician_id == current_user.id`, everyone else sees all tenant jobs).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_jobs_create_list.py
def _owner_token(client, platform_admin, email="owner-job@example.com", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Owner",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def _create_customer_and_asset(client, token):
    customer_id = client.post(
        "/api/v1/customers", json={"name": "Nimal Perera"}, headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Toyota Corolla"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]
    return customer_id, asset_id


def _create_technician(client, owner_token, email="tech-job@example.com"):
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "techpass123"})
    return login.json()["access_token"], login.json()


def test_owner_can_create_a_job(client, platform_admin):
    token = _owner_token(client, platform_admin)
    customer_id, asset_id = _create_customer_and_asset(client, token)

    response = client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Brake pad replacement"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Brake pad replacement"
    assert body["status"] == "open"
    assert body["customer_id"] == customer_id
    assert body["asset_id"] == asset_id


def test_create_job_rejects_unknown_customer(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-job2@example.com")
    _, asset_id = _create_customer_and_asset(client, token)

    response = client.post(
        "/api/v1/jobs",
        json={"customer_id": "does-not-exist", "asset_id": asset_id, "title": "Should fail"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


def test_technician_only_sees_assigned_jobs(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-job3@example.com")
    customer_id, asset_id = _create_customer_and_asset(client, token)
    tech_token, tech_login = _create_technician(client, token, email="tech-job3@example.com")
    tech_id = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tech_token}"}).json()["id"]

    assigned_job = client.post(
        "/api/v1/jobs",
        json={
            "customer_id": customer_id,
            "asset_id": asset_id,
            "title": "Assigned to technician",
            "assigned_technician_id": tech_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Not assigned to anyone"},
        headers={"Authorization": f"Bearer {token}"},
    )

    owner_list = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"}).json()
    tech_list = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {tech_token}"}).json()

    assert owner_list["total"] == 2
    assert tech_list["total"] == 1
    assert tech_list["items"][0]["id"] == assigned_job["id"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `.venv/bin/pytest tests/test_jobs_create_list.py -v`
Expected: FAIL — routes don't exist.

- [ ] **Step 3: Write the schemas**

```python
# backend/app/schemas/job.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job import JobStatus


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    customer_id: str
    asset_id: str
    assigned_technician_id: str | None
    title: str
    description: str | None
    status: JobStatus
    started_at: datetime | None
    completed_at: datetime | None
    labor_cost: float


class JobCreate(BaseModel):
    customer_id: str
    asset_id: str
    title: str
    description: str | None = None
    assigned_technician_id: str | None = None


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assigned_technician_id: str | None = None


class JobListResponse(BaseModel):
    items: list[JobRead]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 4: Write the create + list endpoints**

```python
# backend/app/api/v1/jobs.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.asset import Asset
from app.models.customer import Customer
from app.models.job import Job
from app.models.user import User, UserRole
from app.schemas.job import JobCreate, JobListResponse, JobRead

router = APIRouter()


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    customer = (
        db.query(Customer)
        .filter(Customer.id == payload.customer_id, Customer.tenant_id == current_user.tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    asset = (
        db.query(Asset)
        .filter(Asset.id == payload.asset_id, Asset.tenant_id == current_user.tenant_id)
        .first()
    )
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    job = Job(
        tenant_id=current_user.tenant_id,
        customer_id=payload.customer_id,
        asset_id=payload.asset_id,
        title=payload.title,
        description=payload.description,
        assigned_technician_id=payload.assigned_technician_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> JobListResponse:
    query = db.query(Job).filter(Job.tenant_id == current_user.tenant_id)
    if current_user.role == UserRole.technician:
        query = query.filter(Job.assigned_technician_id == current_user.id)
    total = query.count()
    jobs = query.offset((page - 1) * page_size).limit(page_size).all()
    return JobListResponse(items=jobs, total=total, page=page, page_size=page_size)
```

- [ ] **Step 5: Wire the router**

```python
# backend/app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1 import admin, assets, auth, customers, jobs, users

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(customers.router, tags=["customers"])
api_router.include_router(assets.router, tags=["assets"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(admin.router, tags=["admin"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_jobs_create_list.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all pass, no regressions.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/job.py backend/app/api/v1/jobs.py backend/app/api/v1/router.py backend/tests/test_jobs_create_list.py
git commit -m "feat: add job create and list endpoints with technician filtering"
```

---

## Task 7: Job Detail + Update

**Files:**
- Modify: `backend/app/api/v1/jobs.py`
- Test: `backend/tests/test_jobs_detail_update.py`

**Interfaces:**
- Consumes: everything from Task 6.
- Produces: `app.api.v1.jobs._get_job_or_404(db, current_user, job_id) -> Job` (tenant-scoped, and technician-scoped when the caller is a technician) — Task 8 and Task 9 both reuse this exact helper. `GET /api/v1/jobs/{job_id}` (any authenticated role, technician-filtered same as list). `PATCH /api/v1/jobs/{job_id}` (staff roles only — general field edits; technicians never edit title/description/assignment, only status via Task 8's dedicated endpoint).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_jobs_detail_update.py
def _owner_token(client, platform_admin, email="owner-jobdu@example.com", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Owner",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def _create_job(client, token, title="Brake pad replacement", assigned_technician_id=None):
    customer_id = client.post(
        "/api/v1/customers", json={"name": "Nimal Perera"}, headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Toyota Corolla"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]
    payload = {"customer_id": customer_id, "asset_id": asset_id, "title": title}
    if assigned_technician_id:
        payload["assigned_technician_id"] = assigned_technician_id
    return client.post("/api/v1/jobs", json=payload, headers={"Authorization": f"Bearer {token}"}).json()


def _create_technician(client, owner_token, email="tech-jobdu@example.com"):
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "techpass123"})
    token = login.json()["access_token"]
    tech_id = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]
    return token, tech_id


def test_owner_can_get_and_update_a_job(client, platform_admin):
    token = _owner_token(client, platform_admin)
    job = _create_job(client, token)

    get_response = client.get(f"/api/v1/jobs/{job['id']}", headers={"Authorization": f"Bearer {token}"})
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Brake pad replacement"

    update_response = client.patch(
        f"/api/v1/jobs/{job['id']}",
        json={"description": "Front and rear pads"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Front and rear pads"
    assert update_response.json()["title"] == "Brake pad replacement"


def test_technician_can_view_only_their_own_assigned_job(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-jobdu2@example.com")
    tech_token, tech_id = _create_technician(client, token, email="tech-jobdu2@example.com")
    assigned_job = _create_job(client, token, title="Assigned job", assigned_technician_id=tech_id)
    other_job = _create_job(client, token, title="Someone else's job")

    assigned_response = client.get(
        f"/api/v1/jobs/{assigned_job['id']}", headers={"Authorization": f"Bearer {tech_token}"}
    )
    other_response = client.get(
        f"/api/v1/jobs/{other_job['id']}", headers={"Authorization": f"Bearer {tech_token}"}
    )

    assert assigned_response.status_code == 200
    assert other_response.status_code == 404


def test_technician_cannot_patch_job_fields(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-jobdu3@example.com")
    tech_token, tech_id = _create_technician(client, token, email="tech-jobdu3@example.com")
    job = _create_job(client, token, assigned_technician_id=tech_id)

    response = client.patch(
        f"/api/v1/jobs/{job['id']}",
        json={"title": "Technician trying to rename"},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `.venv/bin/pytest tests/test_jobs_detail_update.py -v`
Expected: FAIL — routes don't exist.

- [ ] **Step 3: Add the detail + update endpoints**

```python
# backend/app/api/v1/jobs.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.asset import Asset
from app.models.customer import Customer
from app.models.job import Job
from app.models.user import User, UserRole
from app.schemas.job import JobCreate, JobListResponse, JobRead, JobUpdate

router = APIRouter()


def _get_job_or_404(db: Session, current_user: User, job_id: str) -> Job:
    query = db.query(Job).filter(Job.id == job_id, Job.tenant_id == current_user.tenant_id)
    if current_user.role == UserRole.technician:
        query = query.filter(Job.assigned_technician_id == current_user.id)
    job = query.first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    customer = (
        db.query(Customer)
        .filter(Customer.id == payload.customer_id, Customer.tenant_id == current_user.tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    asset = (
        db.query(Asset)
        .filter(Asset.id == payload.asset_id, Asset.tenant_id == current_user.tenant_id)
        .first()
    )
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    job = Job(
        tenant_id=current_user.tenant_id,
        customer_id=payload.customer_id,
        asset_id=payload.asset_id,
        title=payload.title,
        description=payload.description,
        assigned_technician_id=payload.assigned_technician_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> JobListResponse:
    query = db.query(Job).filter(Job.tenant_id == current_user.tenant_id)
    if current_user.role == UserRole.technician:
        query = query.filter(Job.assigned_technician_id == current_user.id)
    total = query.count()
    jobs = query.offset((page - 1) * page_size).limit(page_size).all()
    return JobListResponse(items=jobs, total=total, page=page, page_size=page_size)


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    return _get_job_or_404(db, current_user, job_id)


@router.patch("/jobs/{job_id}", response_model=JobRead)
def update_job(
    job_id: str,
    payload: JobUpdate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    job = (
        db.query(Job)
        .filter(Job.id == job_id, Job.tenant_id == current_user.tenant_id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_jobs_detail_update.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/jobs.py backend/tests/test_jobs_detail_update.py
git commit -m "feat: add job detail and update endpoints"
```

---

## Task 8: Job Status Transitions

**Files:**
- Modify: `backend/app/api/v1/jobs.py`
- Modify: `backend/app/schemas/job.py`
- Test: `backend/tests/test_job_status_transitions.py`

**Interfaces:**
- Consumes: `app.api.v1.jobs._get_job_or_404`, `app.db.base._now`
- Produces: `app.schemas.job.JobStatusUpdate` (`{status: JobStatus}`). `PATCH /api/v1/jobs/{job_id}/status` — staff roles or the assigned technician (via `_get_job_or_404`'s existing technician scoping). Only the four transitions listed in Global Constraints are accepted; anything else (including any attempt to set `invoiced`/`paid` manually) returns 400.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_job_status_transitions.py
def _owner_token(client, platform_admin, email="owner-status@example.com", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Owner",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def _create_technician(client, owner_token, email="tech-status@example.com"):
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "techpass123"})
    token = login.json()["access_token"]
    tech_id = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]
    return token, tech_id


def _create_job(client, token, assigned_technician_id=None):
    customer_id = client.post(
        "/api/v1/customers", json={"name": "Nimal Perera"}, headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Toyota Corolla"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]
    payload = {"customer_id": customer_id, "asset_id": asset_id, "title": "Brake pad replacement"}
    if assigned_technician_id:
        payload["assigned_technician_id"] = assigned_technician_id
    return client.post("/api/v1/jobs", json=payload, headers={"Authorization": f"Bearer {token}"}).json()


def test_owner_can_walk_a_job_through_the_happy_path(client, platform_admin):
    token = _owner_token(client, platform_admin)
    job = _create_job(client, token)

    to_in_progress = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert to_in_progress.status_code == 200
    assert to_in_progress.json()["status"] == "in_progress"
    assert to_in_progress.json()["started_at"] is not None

    to_done = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert to_done.status_code == 200
    assert to_done.json()["status"] == "done"
    assert to_done.json()["completed_at"] is not None


def test_cannot_skip_from_open_directly_to_done(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-status2@example.com")
    job = _create_job(client, token)

    response = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


def test_cannot_manually_set_invoiced_status(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-status3@example.com")
    job = _create_job(client, token)
    client.patch(
        f"/api/v1/jobs/{job['id']}/status", json={"status": "in_progress"}, headers={"Authorization": f"Bearer {token}"}
    )
    client.patch(
        f"/api/v1/jobs/{job['id']}/status", json={"status": "done"}, headers={"Authorization": f"Bearer {token}"}
    )

    response = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "invoiced"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


def test_assigned_technician_can_transition_their_own_job(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-status4@example.com")
    tech_token, tech_id = _create_technician(client, token, email="tech-status4@example.com")
    job = _create_job(client, token, assigned_technician_id=tech_id)

    response = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_technician_cannot_transition_an_unassigned_job(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-status5@example.com")
    tech_token, _tech_id = _create_technician(client, token, email="tech-status5@example.com")
    job = _create_job(client, token)

    response = client.patch(
        f"/api/v1/jobs/{job['id']}/status",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `.venv/bin/pytest tests/test_job_status_transitions.py -v`
Expected: FAIL — route doesn't exist.

- [ ] **Step 3: Add the status transition schema**

```python
# backend/app/schemas/job.py
# add this class alongside the existing ones:
class JobStatusUpdate(BaseModel):
    status: JobStatus
```

- [ ] **Step 4: Add the status transition endpoint**

The import block at the top of `backend/app/api/v1/jobs.py` needs two additions: `_now` from `app.db.base`, `JobStatus` alongside the existing `Job` import from `app.models.job`, and `JobStatusUpdate` alongside the existing schema imports. The full, final import block:

```python
# backend/app/api/v1/jobs.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.core.dependencies import get_current_user, require_role
from app.db.base import _now
from app.db.session import get_db
from app.models.asset import Asset
from app.models.customer import Customer
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole
from app.schemas.job import JobCreate, JobListResponse, JobRead, JobStatusUpdate, JobUpdate

router = APIRouter()
```

Add this module-level constant and route to the end of the file:

```python
_MANUAL_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.open: {JobStatus.in_progress, JobStatus.cancelled},
    JobStatus.in_progress: {JobStatus.done, JobStatus.cancelled},
    JobStatus.done: set(),
    JobStatus.invoiced: set(),
    JobStatus.paid: set(),
    JobStatus.cancelled: set(),
}


@router.patch("/jobs/{job_id}/status", response_model=JobRead)
def update_job_status(
    job_id: str,
    payload: JobStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    if current_user.role not in (*STAFF_ROLES, UserRole.technician):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this role")

    job = _get_job_or_404(db, current_user, job_id)

    allowed = _MANUAL_TRANSITIONS.get(job.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition job from {job.status.value} to {payload.status.value}",
        )

    job.status = payload.status
    if payload.status == JobStatus.in_progress and job.started_at is None:
        job.started_at = _now()
    if payload.status == JobStatus.done:
        job.completed_at = _now()
    db.commit()
    db.refresh(job)
    return job
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_job_status_transitions.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all pass, no regressions.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/jobs.py backend/app/schemas/job.py backend/tests/test_job_status_transitions.py
git commit -m "feat: add job status transition enforcement"
```

---

## Task 9: Job Labor Entries

**Files:**
- Create: `backend/app/models/job_labor_entry.py`
- Create: `backend/app/schemas/job_labor_entry.py`
- Modify: `backend/app/api/v1/jobs.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/test_job_labor_entries.py`

**Interfaces:**
- Consumes: `app.api.v1.jobs._get_job_or_404`
- Produces: `app.models.job_labor_entry.JobLaborEntry` — `TenantScopedMixin` fields plus `job_id: str`, `technician_id: str`, `start_time: datetime`, `end_time: datetime | None`, `hourly_rate: float`. `app.schemas.job_labor_entry.JobLaborEntryRead` / `JobLaborEntryCreate`. `POST /api/v1/jobs/{job_id}/labor-entries` — a `technician` may only log time against their own assigned job (using their own `id`, ignoring any `technician_id` in the payload); staff roles may log an entry for any technician on any job in their tenant (e.g. for corrections).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_job_labor_entries.py
def _owner_token(client, platform_admin, email="owner-labor@example.com", password="ownerpass123"):
    admin_login = client.post("/api/v1/admin/auth/login", json=platform_admin)
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/admin/tenants",
        json={
            "name": "Colombo Auto Repair",
            "owner_name": "Owner",
            "owner_email": email,
            "owner_password": password,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def _create_technician(client, owner_token, email="tech-labor@example.com"):
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "techpass123"})
    token = login.json()["access_token"]
    tech_id = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]
    return token, tech_id


def _create_job(client, token, assigned_technician_id=None):
    customer_id = client.post(
        "/api/v1/customers", json={"name": "Nimal Perera"}, headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Toyota Corolla"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]
    payload = {"customer_id": customer_id, "asset_id": asset_id, "title": "Brake pad replacement"}
    if assigned_technician_id:
        payload["assigned_technician_id"] = assigned_technician_id
    return client.post("/api/v1/jobs", json=payload, headers={"Authorization": f"Bearer {token}"}).json()


def test_assigned_technician_can_log_their_own_time(client, platform_admin):
    token = _owner_token(client, platform_admin)
    tech_token, tech_id = _create_technician(client, token)
    job = _create_job(client, token, assigned_technician_id=tech_id)

    response = client.post(
        f"/api/v1/jobs/{job['id']}/labor-entries",
        json={"start_time": "2026-08-01T09:00:00Z", "end_time": "2026-08-01T10:30:00Z", "hourly_rate": 1500.0},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["job_id"] == job["id"]
    assert body["technician_id"] == tech_id
    assert body["hourly_rate"] == 1500.0


def test_technician_cannot_log_time_on_an_unassigned_job(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-labor2@example.com")
    tech_token, _tech_id = _create_technician(client, token, email="tech-labor2@example.com")
    job = _create_job(client, token)

    response = client.post(
        f"/api/v1/jobs/{job['id']}/labor-entries",
        json={"start_time": "2026-08-01T09:00:00Z", "hourly_rate": 1500.0},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 404


def test_owner_can_log_time_for_a_specific_technician(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-labor3@example.com")
    tech_token, tech_id = _create_technician(client, token, email="tech-labor3@example.com")
    job = _create_job(client, token, assigned_technician_id=tech_id)

    response = client.post(
        f"/api/v1/jobs/{job['id']}/labor-entries",
        json={"start_time": "2026-08-01T09:00:00Z", "hourly_rate": 1500.0, "technician_id": tech_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["technician_id"] == tech_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `.venv/bin/pytest tests/test_job_labor_entries.py -v`
Expected: FAIL — route doesn't exist.

- [ ] **Step 3: Write the model**

```python
# backend/app/models/job_labor_entry.py
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class JobLaborEntry(Base, TenantScopedMixin):
    __tablename__ = "job_labor_entries"

    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    technician_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hourly_rate: Mapped[float] = mapped_column(Float, nullable=False)
```

- [ ] **Step 4: Write the schemas**

```python
# backend/app/schemas/job_labor_entry.py
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobLaborEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    technician_id: str
    start_time: datetime
    end_time: datetime | None
    hourly_rate: float


class JobLaborEntryCreate(BaseModel):
    start_time: datetime
    end_time: datetime | None = None
    hourly_rate: float
    technician_id: str | None = None
```

- [ ] **Step 5: Register the model with Alembic**

```python
# backend/alembic/env.py
# change this line:
from app.models import asset, customer, job, platform_admin, tenant, user  # noqa: F401 -- registers models on Base.metadata
# to:
from app.models import asset, customer, job, job_labor_entry, platform_admin, tenant, user  # noqa: F401 -- registers models on Base.metadata
```

- [ ] **Step 6: Add the endpoint**

```python
# backend/app/api/v1/jobs.py
# add these imports to the existing import block:
from app.models.job_labor_entry import JobLaborEntry
from app.schemas.job_labor_entry import JobLaborEntryCreate, JobLaborEntryRead

# add this route at the end of the file:
@router.post(
    "/jobs/{job_id}/labor-entries", response_model=JobLaborEntryRead, status_code=status.HTTP_201_CREATED
)
def create_labor_entry(
    job_id: str,
    payload: JobLaborEntryCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JobLaborEntry:
    if current_user.role not in (*STAFF_ROLES, UserRole.technician):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this role")

    job = (
        db.query(Job)
        .filter(Job.id == job_id, Job.tenant_id == current_user.tenant_id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if current_user.role == UserRole.technician:
        if job.assigned_technician_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        technician_id = current_user.id
    else:
        technician_id = payload.technician_id or current_user.id

    entry = JobLaborEntry(
        tenant_id=current_user.tenant_id,
        job_id=job_id,
        technician_id=technician_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        hourly_rate=payload.hourly_rate,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_job_labor_entries.py -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Generate and apply the migration**

Run (from `backend/`):
```bash
.venv/bin/alembic revision --autogenerate -m "create job_labor_entries table"
.venv/bin/alembic upgrade head
```
Expected: exits 0.

- [ ] **Step 9: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all pass, no regressions. This is the last task in the plan — confirm the total test count makes sense (should be the backend foundation's 37 plus this plan's new tests: 4 customer model/API-ish... count precisely from the actual run output, don't guess a number here).

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/job_labor_entry.py backend/app/schemas/job_labor_entry.py backend/app/api/v1/jobs.py backend/alembic/env.py backend/alembic/versions/ backend/tests/test_job_labor_entries.py
git commit -m "feat: add job labor entry tracking"
```

---

## Definition of Done

- `.venv/bin/pytest -v` (run from `backend/`) passes with zero failures, output pristine aside from the already-tracked upstream FastAPI/Starlette deprecation warnings.
- `alembic upgrade head` applies all new migrations (customers, assets, jobs, job_labor_entries) cleanly.
- Manual smoke test: as an owner, create a customer, an asset for that customer, and a job referencing both; assign a technician; log in as that technician and confirm they see only that one job in `GET /jobs`; walk the job through `open → in_progress → done` via `PATCH /jobs/{id}/status`; log a labor entry as the technician.
- Tenant isolation re-confirmed at every new resource type: a customer/asset/job ID from tenant A returns 404 when queried by a user in tenant B (not just for the top-level list endpoints — by-ID lookups too).
- This plan does not cover: `job_parts` (deferred to the Inventory sub-plan), invoice generation or the `invoiced`/`paid` job statuses (Finance sub-plan), or any mobile app work (later sub-plans).
