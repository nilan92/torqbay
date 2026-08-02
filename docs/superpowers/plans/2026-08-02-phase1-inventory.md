# Phase 1 Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full inventory management — suppliers, stocked items, parts consumed on jobs (stock out), and purchase orders (stock in) — to the Torqbay backend.

**Architecture:** Follows the existing tenant-scoped REST pattern exactly: SQLAlchemy models on `TenantScopedMixin`, Pydantic schemas, one router module per resource group mounted in `app/api/v1/router.py`. `inventory_items.quantity_on_hand` has exactly two write paths — recording parts on a job decrements it, receiving a purchase order increments it. No other code path may mutate stock.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (`Mapped`/`mapped_column`), Alembic, MySQL 8 in production, in-memory SQLite for tests.

## Global Constraints

- `tenant_id` is **always** taken from `current_user.tenant_id`, never from request input.
- Every tenant-owned model inherits `TenantScopedMixin` from `app.db.base` (supplies `id`, `tenant_id`, `created_at`, `updated_at`, `deleted_at`).
- Reuse `STAFF_ROLES` by importing it from `app.api.v1.customers` — do not redefine it.
- Write access to inventory is `STAFF_ROLES` (`owner`, `manager`, `frontdesk`). Read access additionally includes `technician`, per the permission table in `docs/04-api-design.md`.
- List endpoints use the established pagination contract: `page: int = Query(1, ge=1)`, `page_size: int = Query(20, ge=1, le=100)`, returning `{items, total, page, page_size}`.
- A missing or cross-tenant resource returns **404**, never 403 — never leak existence across tenants.
- Money and quantity columns use `Float`, matching the existing `labor_cost` / `hourly_rate` convention. Do not introduce `Numeric` in this plan.
- Every stock mutation reads its `InventoryItem` row with `.with_for_update()`. On MySQL this takes a row lock; on SQLite it is a harmless no-op.
- Tests use the `client` and `platform_admin` fixtures from `backend/tests/conftest.py`.
- Run tests with `cd backend && .venv/bin/python -m pytest`.
- Migrations: generate with `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "<message>"`, then **read the generated file and correct it**. Current head is `be92032f8ef8`.

---

### Task 1: Supplier model and migration

**Files:**
- Create: `backend/app/models/supplier.py`
- Create: `backend/alembic/versions/<generated>_create_suppliers_table.py`
- Test: `backend/tests/test_supplier_model.py`

**Interfaces:**
- Consumes: `Base`, `TenantScopedMixin` from `app.db.base`
- Produces: `Supplier` with `__tablename__ = "suppliers"`, columns `name: str`, `contact_info: str | None`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_supplier_model.py`:

```python
from app.models.supplier import Supplier
from app.models.tenant import Tenant


def _tenant(db_session):
    tenant = Tenant(name="Colombo Auto Repair")
    db_session.add(tenant)
    db_session.commit()
    return tenant


def test_supplier_persists_with_tenant_scope(db_session):
    tenant = _tenant(db_session)

    supplier = Supplier(tenant_id=tenant.id, name="Lanka Parts Ltd", contact_info="011-2345678")
    db_session.add(supplier)
    db_session.commit()

    stored = db_session.query(Supplier).one()
    assert stored.id is not None
    assert stored.tenant_id == tenant.id
    assert stored.name == "Lanka Parts Ltd"
    assert stored.contact_info == "011-2345678"
    assert stored.created_at is not None
    assert stored.deleted_at is None


def test_supplier_contact_info_is_optional(db_session):
    tenant = _tenant(db_session)

    supplier = Supplier(tenant_id=tenant.id, name="Walk-in Supplier")
    db_session.add(supplier)
    db_session.commit()

    assert db_session.query(Supplier).one().contact_info is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_supplier_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.supplier'`

- [ ] **Step 3: Write the model**

Create `backend/app/models/supplier.py`:

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class Supplier(Base, TenantScopedMixin):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

- [ ] **Step 4: Register the model so Alembic sees it**

Model registration happens in `backend/alembic/env.py`, which imports every model module explicitly. `backend/app/models/__init__.py` is intentionally empty — leave it that way.

Add `supplier` to the existing enumerated import on line 8 of `backend/alembic/env.py`, keeping alphabetical order:

```python
from app.models import asset, customer, job, job_labor_entry, platform_admin, supplier, tenant, user  # noqa: F401 -- registers models on Base.metadata
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_supplier_model.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Generate and verify the migration**

Run: `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "create suppliers table"`

Open the generated file. Confirm it creates the `suppliers` table with all `TenantScopedMixin` columns, a foreign key to `tenants.id`, and an index on `tenant_id`. Confirm `down_revision = 'be92032f8ef8'`. Then verify it applies cleanly:

Run: `cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic downgrade -1 && .venv/bin/python -m alembic upgrade head`
Expected: all three succeed with no error

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/supplier.py backend/app/models/__init__.py backend/alembic/versions/ backend/tests/test_supplier_model.py
git commit -m "feat(inventory): add Supplier model and migration"
```

---

### Task 2: Supplier endpoints

**Files:**
- Create: `backend/app/schemas/supplier.py`
- Create: `backend/app/api/v1/suppliers.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_suppliers_api.py`

**Interfaces:**
- Consumes: `Supplier`, `STAFF_ROLES` from `app.api.v1.customers`, `require_role`, `get_db`
- Produces: `_get_supplier_or_404(db, tenant_id, supplier_id) -> Supplier` (later tasks import this); routes `POST/GET /suppliers`, `GET/PATCH /suppliers/{supplier_id}`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_suppliers_api.py`:

```python
def _owner_token(client, platform_admin, email="owner-supplier@example.com", password="ownerpass123"):
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


def test_owner_can_create_and_list_suppliers(client, platform_admin):
    token = _owner_token(client, platform_admin)

    create_response = client.post(
        "/api/v1/suppliers",
        json={"name": "Lanka Parts Ltd", "contact_info": "011-2345678"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    assert create_response.json()["name"] == "Lanka Parts Ltd"

    list_response = client.get("/api/v1/suppliers", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["items"][0]["contact_info"] == "011-2345678"


def test_supplier_can_be_fetched_and_updated(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-supplier-2@example.com")
    supplier_id = client.post(
        "/api/v1/suppliers",
        json={"name": "Old Name"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]

    get_response = client.get(
        f"/api/v1/suppliers/{supplier_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 200

    patch_response = client.patch(
        f"/api/v1/suppliers/{supplier_id}",
        json={"name": "New Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "New Name"


def test_supplier_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-supplier-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-supplier-b@example.com")
    supplier_id = client.post(
        "/api/v1/suppliers",
        json={"name": "Tenant A Supplier"},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()["id"]

    response = client.get(
        f"/api/v1/suppliers/{supplier_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response.status_code == 404


def test_creating_a_supplier_requires_authentication(client):
    response = client.post("/api/v1/suppliers", json={"name": "No Auth"})
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_suppliers_api.py -v`
Expected: FAIL — all requests 404, since the routes do not exist

- [ ] **Step 3: Write the schemas**

Create `backend/app/schemas/supplier.py`:

```python
from pydantic import BaseModel, ConfigDict


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    contact_info: str | None


class SupplierCreate(BaseModel):
    name: str
    contact_info: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact_info: str | None = None


class SupplierListResponse(BaseModel):
    items: list[SupplierRead]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 4: Write the router**

Create `backend/app/api/v1/suppliers.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.supplier import (
    SupplierCreate,
    SupplierListResponse,
    SupplierRead,
    SupplierUpdate,
)

router = APIRouter()


def _get_supplier_or_404(db: Session, tenant_id: str, supplier_id: str) -> Supplier:
    supplier = (
        db.query(Supplier)
        .filter(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id)
        .first()
    )
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return supplier


@router.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Supplier:
    supplier = Supplier(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/suppliers", response_model=SupplierListResponse)
def list_suppliers(
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SupplierListResponse:
    query = db.query(Supplier).filter(Supplier.tenant_id == current_user.tenant_id)
    total = query.count()
    suppliers = query.offset((page - 1) * page_size).limit(page_size).all()
    return SupplierListResponse(items=suppliers, total=total, page=page, page_size=page_size)


@router.get("/suppliers/{supplier_id}", response_model=SupplierRead)
def get_supplier(
    supplier_id: str,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Supplier:
    return _get_supplier_or_404(db, current_user.tenant_id, supplier_id)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: str,
    payload: SupplierUpdate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Supplier:
    supplier = _get_supplier_or_404(db, current_user.tenant_id, supplier_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier
```

- [ ] **Step 5: Mount the router**

In `backend/app/api/v1/router.py`, add `suppliers` to the existing import and add one `include_router` line, keeping the file's existing ordering style:

```python
from app.api.v1 import admin, assets, auth, customers, jobs, suppliers, users
```

```python
api_router.include_router(suppliers.router, tags=["suppliers"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_suppliers_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/supplier.py backend/app/api/v1/suppliers.py backend/app/api/v1/router.py backend/tests/test_suppliers_api.py
git commit -m "feat(inventory): add supplier endpoints"
```

---

### Task 3: InventoryItem model and migration

**Files:**
- Create: `backend/app/models/inventory_item.py`
- Create: `backend/alembic/versions/<generated>_create_inventory_items_table.py`
- Test: `backend/tests/test_inventory_item_model.py`

**Interfaces:**
- Consumes: `Base`, `TenantScopedMixin`; FK to `suppliers.id` from Task 1
- Produces: `InventoryItem` with `__tablename__ = "inventory_items"`, columns `sku`, `name`, `category`, `unit_cost`, `unit_price`, `quantity_on_hand`, `reorder_threshold`, `supplier_id`. Unique constraint `uq_inventory_items_tenant_sku` on `(tenant_id, sku)`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_inventory_item_model.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.inventory_item import InventoryItem
from app.models.supplier import Supplier
from app.models.tenant import Tenant


def _tenant(db_session, name="Colombo Auto Repair"):
    tenant = Tenant(name=name)
    db_session.add(tenant)
    db_session.commit()
    return tenant


def test_inventory_item_defaults_quantity_and_threshold_to_zero(db_session):
    tenant = _tenant(db_session)

    item = InventoryItem(
        tenant_id=tenant.id, sku="BP-001", name="Brake pad set", unit_cost=2500.0, unit_price=4000.0
    )
    db_session.add(item)
    db_session.commit()

    stored = db_session.query(InventoryItem).one()
    assert stored.quantity_on_hand == 0.0
    assert stored.reorder_threshold == 0.0
    assert stored.category is None
    assert stored.supplier_id is None


def test_inventory_item_can_link_a_supplier(db_session):
    tenant = _tenant(db_session)
    supplier = Supplier(tenant_id=tenant.id, name="Lanka Parts Ltd")
    db_session.add(supplier)
    db_session.commit()

    item = InventoryItem(
        tenant_id=tenant.id,
        sku="OF-010",
        name="Oil filter",
        category="Filters",
        unit_cost=800.0,
        unit_price=1500.0,
        quantity_on_hand=12.0,
        reorder_threshold=4.0,
        supplier_id=supplier.id,
    )
    db_session.add(item)
    db_session.commit()

    stored = db_session.query(InventoryItem).one()
    assert stored.supplier_id == supplier.id
    assert stored.category == "Filters"
    assert stored.quantity_on_hand == 12.0


def test_sku_is_unique_within_a_tenant(db_session):
    tenant = _tenant(db_session)
    db_session.add(
        InventoryItem(tenant_id=tenant.id, sku="DUP-1", name="First", unit_cost=1.0, unit_price=2.0)
    )
    db_session.commit()

    db_session.add(
        InventoryItem(tenant_id=tenant.id, sku="DUP-1", name="Second", unit_cost=1.0, unit_price=2.0)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_same_sku_is_allowed_in_a_different_tenant(db_session):
    tenant_a = _tenant(db_session, name="Tenant A")
    tenant_b = _tenant(db_session, name="Tenant B")

    db_session.add(
        InventoryItem(tenant_id=tenant_a.id, sku="SHARED-1", name="A", unit_cost=1.0, unit_price=2.0)
    )
    db_session.add(
        InventoryItem(tenant_id=tenant_b.id, sku="SHARED-1", name="B", unit_cost=1.0, unit_price=2.0)
    )
    db_session.commit()

    assert db_session.query(InventoryItem).count() == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_inventory_item_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.inventory_item'`

- [ ] **Step 3: Write the model**

Create `backend/app/models/inventory_item.py`:

```python
from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class InventoryItem(Base, TenantScopedMixin):
    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint("tenant_id", "sku", name="uq_inventory_items_tenant_sku"),)

    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity_on_hand: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0", nullable=False
    )
    reorder_threshold: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0", nullable=False
    )
    supplier_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("suppliers.id"), nullable=True, index=True
    )
```

- [ ] **Step 4: Register the model**

Add `inventory_item` to the enumerated import on line 8 of `backend/alembic/env.py`, keeping alphabetical order. Leave `backend/app/models/__init__.py` empty — it is not the registration point.

```python
from app.models import asset, customer, inventory_item, job, job_labor_entry, platform_admin, supplier, tenant, user  # noqa: F401 -- registers models on Base.metadata
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_inventory_item_model.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Generate and verify the migration**

Run: `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "create inventory_items table"`

Open the generated file. Confirm the unique constraint `uq_inventory_items_tenant_sku` is present — autogenerate sometimes omits constraints declared in `__table_args__`. If missing, add it manually inside `op.create_table(...)`:

```python
sa.UniqueConstraint('tenant_id', 'sku', name='uq_inventory_items_tenant_sku'),
```

Run: `cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic downgrade -1 && .venv/bin/python -m alembic upgrade head`
Expected: all three succeed

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/inventory_item.py backend/app/models/__init__.py backend/alembic/versions/ backend/tests/test_inventory_item_model.py
git commit -m "feat(inventory): add InventoryItem model and migration"
```

---

### Task 4: Inventory item endpoints

**Files:**
- Create: `backend/app/schemas/inventory_item.py`
- Create: `backend/app/api/v1/inventory_items.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_inventory_items_api.py`

**Interfaces:**
- Consumes: `InventoryItem`, `_get_supplier_or_404` from `app.api.v1.suppliers`, `STAFF_ROLES`
- Produces: `INVENTORY_READ_ROLES` and `_get_item_or_404(db, tenant_id, item_id) -> InventoryItem` (later tasks import both); routes `POST/GET /inventory-items`, `GET/PATCH /inventory-items/{item_id}`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_inventory_items_api.py`:

```python
def _owner_token(client, platform_admin, email="owner-item@example.com", password="ownerpass123"):
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


def _create_item(client, token, sku="BP-001", **overrides):
    payload = {"sku": sku, "name": "Brake pad set", "unit_cost": 2500.0, "unit_price": 4000.0}
    payload.update(overrides)
    return client.post(
        "/api/v1/inventory-items", json=payload, headers={"Authorization": f"Bearer {token}"}
    )


def test_owner_can_create_and_list_inventory_items(client, platform_admin):
    token = _owner_token(client, platform_admin)

    create_response = _create_item(client, token, quantity_on_hand=10.0, reorder_threshold=3.0)
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["sku"] == "BP-001"
    assert body["quantity_on_hand"] == 10.0

    list_response = client.get("/api/v1/inventory-items", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_quantity_and_threshold_default_to_zero(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-item-default@example.com")

    body = _create_item(client, token).json()
    assert body["quantity_on_hand"] == 0.0
    assert body["reorder_threshold"] == 0.0


def test_duplicate_sku_in_same_tenant_returns_409(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-item-dup@example.com")
    assert _create_item(client, token, sku="SAME").status_code == 201

    response = _create_item(client, token, sku="SAME")
    assert response.status_code == 409


def test_item_can_be_updated(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-item-patch@example.com")
    item_id = _create_item(client, token).json()["id"]

    response = client.patch(
        f"/api/v1/inventory-items/{item_id}",
        json={"unit_price": 4500.0, "reorder_threshold": 5.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["unit_price"] == 4500.0
    assert response.json()["reorder_threshold"] == 5.0


def test_patch_cannot_change_quantity_on_hand(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-item-qty@example.com")
    item_id = _create_item(client, token, quantity_on_hand=7.0).json()["id"]

    response = client.patch(
        f"/api/v1/inventory-items/{item_id}",
        json={"quantity_on_hand": 999.0},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["quantity_on_hand"] == 7.0


def test_creating_item_with_supplier_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-item-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-item-b@example.com")
    supplier_id = client.post(
        "/api/v1/suppliers",
        json={"name": "Tenant A Supplier"},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()["id"]

    response = _create_item(client, token_b, sku="X-1", supplier_id=supplier_id)
    assert response.status_code == 404


def test_item_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-item-iso-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-item-iso-b@example.com")
    item_id = _create_item(client, token_a).json()["id"]

    response = client.get(
        f"/api/v1/inventory-items/{item_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_inventory_items_api.py -v`
Expected: FAIL — routes do not exist

- [ ] **Step 3: Write the schemas**

Create `backend/app/schemas/inventory_item.py`. Note `InventoryItemUpdate` deliberately omits `quantity_on_hand` — stock is only mutated by recording job parts or receiving a purchase order.

```python
from pydantic import BaseModel, ConfigDict


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    sku: str
    name: str
    category: str | None
    unit_cost: float
    unit_price: float
    quantity_on_hand: float
    reorder_threshold: float
    supplier_id: str | None


class InventoryItemCreate(BaseModel):
    sku: str
    name: str
    category: str | None = None
    unit_cost: float
    unit_price: float
    quantity_on_hand: float = 0.0
    reorder_threshold: float = 0.0
    supplier_id: str | None = None


class InventoryItemUpdate(BaseModel):
    sku: str | None = None
    name: str | None = None
    category: str | None = None
    unit_cost: float | None = None
    unit_price: float | None = None
    reorder_threshold: float | None = None
    supplier_id: str | None = None


class InventoryItemListResponse(BaseModel):
    items: list[InventoryItemRead]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 4: Write the router**

Create `backend/app/api/v1/inventory_items.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.api.v1.suppliers import _get_supplier_or_404
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.inventory_item import InventoryItem
from app.models.user import User, UserRole
from app.schemas.inventory_item import (
    InventoryItemCreate,
    InventoryItemListResponse,
    InventoryItemRead,
    InventoryItemUpdate,
)

router = APIRouter()

INVENTORY_READ_ROLES = (*STAFF_ROLES, UserRole.technician)


def _get_item_or_404(db: Session, tenant_id: str, item_id: str) -> InventoryItem:
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.id == item_id, InventoryItem.tenant_id == tenant_id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
    return item


def _reject_duplicate_sku(db: Session, tenant_id: str, sku: str, exclude_id: str | None = None) -> None:
    query = db.query(InventoryItem).filter(
        InventoryItem.tenant_id == tenant_id, InventoryItem.sku == sku
    )
    if exclude_id is not None:
        query = query.filter(InventoryItem.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An item with this SKU already exists"
        )


@router.post("/inventory-items", response_model=InventoryItemRead, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    payload: InventoryItemCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> InventoryItem:
    _reject_duplicate_sku(db, current_user.tenant_id, payload.sku)
    if payload.supplier_id is not None:
        _get_supplier_or_404(db, current_user.tenant_id, payload.supplier_id)

    item = InventoryItem(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/inventory-items", response_model=InventoryItemListResponse)
def list_inventory_items(
    current_user: Annotated[User, Depends(require_role(*INVENTORY_READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> InventoryItemListResponse:
    query = db.query(InventoryItem).filter(InventoryItem.tenant_id == current_user.tenant_id)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return InventoryItemListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/inventory-items/{item_id}", response_model=InventoryItemRead)
def get_inventory_item(
    item_id: str,
    current_user: Annotated[User, Depends(require_role(*INVENTORY_READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> InventoryItem:
    return _get_item_or_404(db, current_user.tenant_id, item_id)


@router.patch("/inventory-items/{item_id}", response_model=InventoryItemRead)
def update_inventory_item(
    item_id: str,
    payload: InventoryItemUpdate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> InventoryItem:
    item = _get_item_or_404(db, current_user.tenant_id, item_id)
    updates = payload.model_dump(exclude_unset=True)

    if "sku" in updates:
        _reject_duplicate_sku(db, current_user.tenant_id, updates["sku"], exclude_id=item_id)
    if updates.get("supplier_id") is not None:
        _get_supplier_or_404(db, current_user.tenant_id, updates["supplier_id"])

    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item
```

- [ ] **Step 5: Mount the router**

In `backend/app/api/v1/router.py`, add `inventory_items` to the import and mount it:

```python
api_router.include_router(inventory_items.router, tags=["inventory"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_inventory_items_api.py -v`
Expected: PASS (7 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/inventory_item.py backend/app/api/v1/inventory_items.py backend/app/api/v1/router.py backend/tests/test_inventory_items_api.py
git commit -m "feat(inventory): add inventory item endpoints"
```

---

### Task 5: Low-stock filter

**Files:**
- Modify: `backend/app/api/v1/inventory_items.py`
- Test: `backend/tests/test_inventory_low_stock.py`

**Interfaces:**
- Consumes: `list_inventory_items` from Task 4
- Produces: `GET /inventory-items?low_stock=true` returning only items where `quantity_on_hand <= reorder_threshold`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_inventory_low_stock.py`:

```python
def _owner_token(client, platform_admin, email="owner-lowstock@example.com", password="ownerpass123"):
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


def _create_item(client, token, sku, quantity_on_hand, reorder_threshold):
    return client.post(
        "/api/v1/inventory-items",
        json={
            "sku": sku,
            "name": f"Item {sku}",
            "unit_cost": 100.0,
            "unit_price": 200.0,
            "quantity_on_hand": quantity_on_hand,
            "reorder_threshold": reorder_threshold,
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def test_low_stock_filter_returns_only_items_at_or_below_threshold(client, platform_admin):
    token = _owner_token(client, platform_admin)
    _create_item(client, token, "PLENTY", quantity_on_hand=20.0, reorder_threshold=5.0)
    _create_item(client, token, "AT-THRESHOLD", quantity_on_hand=5.0, reorder_threshold=5.0)
    _create_item(client, token, "BELOW", quantity_on_hand=1.0, reorder_threshold=5.0)

    response = client.get(
        "/api/v1/inventory-items?low_stock=true", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["sku"] for item in body["items"]} == {"AT-THRESHOLD", "BELOW"}


def test_without_the_filter_all_items_are_returned(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-lowstock-all@example.com")
    _create_item(client, token, "PLENTY", quantity_on_hand=20.0, reorder_threshold=5.0)
    _create_item(client, token, "BELOW", quantity_on_hand=1.0, reorder_threshold=5.0)

    response = client.get("/api/v1/inventory-items", headers={"Authorization": f"Bearer {token}"})

    assert response.json()["total"] == 2


def test_low_stock_false_returns_all_items(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-lowstock-false@example.com")
    _create_item(client, token, "PLENTY", quantity_on_hand=20.0, reorder_threshold=5.0)
    _create_item(client, token, "BELOW", quantity_on_hand=1.0, reorder_threshold=5.0)

    response = client.get(
        "/api/v1/inventory-items?low_stock=false", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.json()["total"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_inventory_low_stock.py -v`
Expected: FAIL — `test_low_stock_filter_returns_only_items_at_or_below_threshold` gets `total == 3`, because the unknown query parameter is ignored

- [ ] **Step 3: Add the filter**

In `backend/app/api/v1/inventory_items.py`, change `list_inventory_items` to accept `low_stock` and apply it. Replace the existing function body's query construction:

```python
@router.get("/inventory-items", response_model=InventoryItemListResponse)
def list_inventory_items(
    current_user: Annotated[User, Depends(require_role(*INVENTORY_READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    low_stock: bool = Query(False),
) -> InventoryItemListResponse:
    query = db.query(InventoryItem).filter(InventoryItem.tenant_id == current_user.tenant_id)
    if low_stock:
        query = query.filter(InventoryItem.quantity_on_hand <= InventoryItem.reorder_threshold)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return InventoryItemListResponse(items=items, total=total, page=page, page_size=page_size)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_inventory_low_stock.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/inventory_items.py backend/tests/test_inventory_low_stock.py
git commit -m "feat(inventory): add low_stock filter to item listing"
```

---

### Task 6: JobPart model and migration

**Files:**
- Create: `backend/app/models/job_part.py`
- Create: `backend/alembic/versions/<generated>_create_job_parts_table.py`
- Test: `backend/tests/test_job_part_model.py`

**Interfaces:**
- Consumes: FKs to `jobs.id` and `inventory_items.id`
- Produces: `JobPart` with `__tablename__ = "job_parts"`, columns `job_id`, `inventory_item_id`, `quantity`, `unit_cost_at_time`, `unit_price_at_time`, `overdrawn`, `shortfall`

The `unit_cost_at_time` / `unit_price_at_time` columns are snapshots taken when the part is recorded, so later price changes never retroactively alter past job profitability. `overdrawn` and `shortfall` record that stock was insufficient at the time of use — see Task 7.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_job_part_model.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_job_part_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.job_part'`

- [ ] **Step 3: Write the model**

Create `backend/app/models/job_part.py`:

```python
from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class JobPart(Base, TenantScopedMixin):
    __tablename__ = "job_parts"

    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    inventory_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit_cost_at_time: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_at_time: Mapped[float] = mapped_column(Float, nullable=False)
    overdrawn: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    shortfall: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
```

- [ ] **Step 4: Register the model**

Add `job_part` to the enumerated import on line 8 of `backend/alembic/env.py`, keeping alphabetical order. Leave `backend/app/models/__init__.py` empty — it is not the registration point.

```python
from app.models import asset, customer, inventory_item, job, job_labor_entry, job_part, platform_admin, supplier, tenant, user  # noqa: F401 -- registers models on Base.metadata
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_job_part_model.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Generate and verify the migration**

Run: `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "create job_parts table"`

Verify foreign keys to `jobs.id`, `inventory_items.id`, and `tenants.id` are present, then:

Run: `cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic downgrade -1 && .venv/bin/python -m alembic upgrade head`
Expected: all three succeed

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/job_part.py backend/app/models/__init__.py backend/alembic/versions/ backend/tests/test_job_part_model.py
git commit -m "feat(inventory): add JobPart model and migration"
```

---

### Task 7: Record parts on a job (stock out)

**Files:**
- Modify: `backend/app/api/v1/jobs.py`
- Create: `backend/app/schemas/job_part.py`
- Test: `backend/tests/test_job_parts_api.py`

**Interfaces:**
- Consumes: `_get_job_or_404` from `app.api.v1.jobs`, `_get_item_or_404` from `app.api.v1.inventory_items`, `STAFF_ROLES`
- Produces: `POST /jobs/{job_id}/parts`

**Stock rule.** Stock is decremented by the recorded quantity but **clamped at zero** — `quantity_on_hand` never goes negative. When the requested quantity exceeds what is on hand, the part is still recorded in full (the workshop really did use it), and the shortfall is flagged on the `JobPart` row for later reconciliation:

```
available  = item.quantity_on_hand
shortfall  = max(0, quantity - available)
new_on_hand = max(0, available - quantity)
overdrawn  = shortfall > 0
```

The item row is read with `.with_for_update()` so concurrent decrements serialize on MySQL.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_job_parts_api.py`:

```python
def _owner_token(client, platform_admin, email="owner-jobpart@example.com", password="ownerpass123"):
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


def _job(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": "Nimal"}, headers=headers).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Corolla"},
        headers=headers,
    ).json()["id"]
    return client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Brake service"},
        headers=headers,
    ).json()["id"]


def _item(client, token, sku="BP-001", quantity_on_hand=10.0):
    return client.post(
        "/api/v1/inventory-items",
        json={
            "sku": sku,
            "name": "Brake pad set",
            "unit_cost": 2500.0,
            "unit_price": 4000.0,
            "quantity_on_hand": quantity_on_hand,
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def _on_hand(client, token, item_id):
    return client.get(
        f"/api/v1/inventory-items/{item_id}", headers={"Authorization": f"Bearer {token}"}
    ).json()["quantity_on_hand"]


def test_recording_a_part_decrements_stock_and_snapshots_prices(client, platform_admin):
    token = _owner_token(client, platform_admin)
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    item_id = _item(client, token, quantity_on_hand=10.0)

    response = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 3.0},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == 3.0
    assert body["unit_cost_at_time"] == 2500.0
    assert body["unit_price_at_time"] == 4000.0
    assert body["overdrawn"] is False
    assert body["shortfall"] == 0.0
    assert _on_hand(client, token, item_id) == 7.0


def test_later_price_change_does_not_alter_recorded_snapshot(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-jobpart-snap@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    item_id = _item(client, token)

    part = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 1.0},
        headers=headers,
    ).json()

    client.patch(
        f"/api/v1/inventory-items/{item_id}", json={"unit_price": 9999.0}, headers=headers
    )

    assert part["unit_price_at_time"] == 4000.0


def test_using_more_than_on_hand_clamps_at_zero_and_flags_overdrawn(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-jobpart-over@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    item_id = _item(client, token, quantity_on_hand=2.0)

    response = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 5.0},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == 5.0
    assert body["overdrawn"] is True
    assert body["shortfall"] == 3.0
    assert _on_hand(client, token, item_id) == 0.0


def test_quantity_must_be_positive(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-jobpart-zero@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    item_id = _item(client, token)

    response = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 0},
        headers=headers,
    )

    assert response.status_code == 422


def test_item_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-jobpart-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-jobpart-b@example.com")
    job_id = _job(client, token_a)
    foreign_item_id = _item(client, token_b, sku="B-1")

    response = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": foreign_item_id, "quantity": 1.0},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 404


def test_job_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-jobpart-j-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-jobpart-j-b@example.com")
    job_id = _job(client, token_a)
    item_id = _item(client, token_b, sku="B-2")

    response = client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 1.0},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_job_parts_api.py -v`
Expected: FAIL — route does not exist

- [ ] **Step 3: Write the schemas**

Create `backend/app/schemas/job_part.py`:

```python
from pydantic import BaseModel, ConfigDict, Field


class JobPartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    job_id: str
    inventory_item_id: str
    quantity: float
    unit_cost_at_time: float
    unit_price_at_time: float
    overdrawn: bool
    shortfall: float


class JobPartCreate(BaseModel):
    inventory_item_id: str
    quantity: float = Field(gt=0)


class JobPartListResponse(BaseModel):
    items: list[JobPartRead]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 4: Add the endpoint**

In `backend/app/api/v1/jobs.py`, add these four imports alongside the existing ones:

```python
from app.api.v1.inventory_items import _get_item_or_404
from app.models.inventory_item import InventoryItem
from app.models.job_part import JobPart
from app.schemas.job_part import JobPartCreate, JobPartRead
```

Then append this endpoint to the end of the file:

```python
@router.post("/jobs/{job_id}/parts", response_model=JobPartRead, status_code=status.HTTP_201_CREATED)
def create_job_part(
    job_id: str,
    payload: JobPartCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> JobPart:
    _get_job_or_404(db, current_user, job_id)
    _get_item_or_404(db, current_user.tenant_id, payload.inventory_item_id)

    # Re-read under a row lock so concurrent decrements serialize on MySQL.
    # SQLite ignores FOR UPDATE, which is harmless for the test suite.
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == payload.inventory_item_id,
            InventoryItem.tenant_id == current_user.tenant_id,
        )
        .with_for_update()
        .one()
    )

    available = item.quantity_on_hand
    shortfall = max(0.0, payload.quantity - available)
    item.quantity_on_hand = max(0.0, available - payload.quantity)

    part = JobPart(
        tenant_id=current_user.tenant_id,
        job_id=job_id,
        inventory_item_id=item.id,
        quantity=payload.quantity,
        unit_cost_at_time=item.unit_cost,
        unit_price_at_time=item.unit_price,
        overdrawn=shortfall > 0,
        shortfall=shortfall,
    )
    db.add(part)
    db.commit()
    db.refresh(part)
    return part
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_job_parts_api.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/job_part.py backend/app/api/v1/jobs.py backend/tests/test_job_parts_api.py
git commit -m "feat(inventory): record parts on a job and decrement stock"
```

---

### Task 8: List parts on a job

**Files:**
- Modify: `backend/app/api/v1/jobs.py`
- Test: `backend/tests/test_job_parts_list.py`

**Interfaces:**
- Consumes: `JobPart`, `JobPartListResponse`, `_get_job_or_404`
- Produces: `GET /jobs/{job_id}/parts`

Read access uses `get_current_user` rather than `require_role(*STAFF_ROLES)` so that `_get_job_or_404`'s own technician scoping applies — matching how `get_job` and `list_jobs` already work.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_job_parts_list.py`:

```python
def _owner_token(client, platform_admin, email="owner-partlist@example.com", password="ownerpass123"):
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


def _job(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": "Nimal"}, headers=headers).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Corolla"},
        headers=headers,
    ).json()["id"]
    return client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Brake service"},
        headers=headers,
    ).json()["id"]


def _item(client, token, sku):
    return client.post(
        "/api/v1/inventory-items",
        json={
            "sku": sku,
            "name": f"Item {sku}",
            "unit_cost": 100.0,
            "unit_price": 200.0,
            "quantity_on_hand": 50.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def test_listing_parts_returns_only_that_jobs_parts(client, platform_admin):
    token = _owner_token(client, platform_admin)
    headers = {"Authorization": f"Bearer {token}"}
    job_a = _job(client, token)
    job_b = _job(client, token)
    item_id = _item(client, token, "SHARED")

    client.post(
        f"/api/v1/jobs/{job_a}/parts",
        json={"inventory_item_id": item_id, "quantity": 2.0},
        headers=headers,
    )
    client.post(
        f"/api/v1/jobs/{job_b}/parts",
        json={"inventory_item_id": item_id, "quantity": 5.0},
        headers=headers,
    )

    response = client.get(f"/api/v1/jobs/{job_a}/parts", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["quantity"] == 2.0


def test_listing_parts_for_another_tenants_job_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-partlist-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-partlist-b@example.com")
    job_id = _job(client, token_a)

    response = client.get(
        f"/api/v1/jobs/{job_id}/parts", headers={"Authorization": f"Bearer {token_b}"}
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_job_parts_list.py -v`
Expected: FAIL — route does not exist

- [ ] **Step 3: Add the endpoint**

Add `JobPartListResponse` to the `app.schemas.job_part` import in `backend/app/api/v1/jobs.py`, then append:

```python
@router.get("/jobs/{job_id}/parts", response_model=JobPartListResponse)
def list_job_parts(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> JobPartListResponse:
    _get_job_or_404(db, current_user, job_id)
    query = db.query(JobPart).filter(
        JobPart.tenant_id == current_user.tenant_id, JobPart.job_id == job_id
    )
    total = query.count()
    parts = query.offset((page - 1) * page_size).limit(page_size).all()
    return JobPartListResponse(items=parts, total=total, page=page, page_size=page_size)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_job_parts_list.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/jobs.py backend/tests/test_job_parts_list.py
git commit -m "feat(inventory): list parts recorded on a job"
```

---

### Task 9: PurchaseOrder and PurchaseOrderItem models and migration

**Files:**
- Create: `backend/app/models/purchase_order.py`
- Create: `backend/app/models/purchase_order_item.py`
- Create: `backend/alembic/versions/<generated>_create_purchase_orders_tables.py`
- Test: `backend/tests/test_purchase_order_model.py`

**Interfaces:**
- Consumes: FKs to `suppliers.id`, `purchase_orders.id`, `inventory_items.id`
- Produces: `PurchaseOrderStatus(str, enum.Enum)` with `draft`/`ordered`/`received`; `PurchaseOrder` (`supplier_id`, `status`, `received_at`); `PurchaseOrderItem` (`purchase_order_id`, `inventory_item_id`, `quantity`, `unit_cost`)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_purchase_order_model.py`:

```python
from app.models.inventory_item import InventoryItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderStatus
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier import Supplier
from app.models.tenant import Tenant


def _setup(db_session):
    tenant = Tenant(name="Colombo Auto Repair")
    db_session.add(tenant)
    db_session.commit()

    supplier = Supplier(tenant_id=tenant.id, name="Lanka Parts Ltd")
    item = InventoryItem(
        tenant_id=tenant.id, sku="BP-001", name="Brake pad set", unit_cost=2500.0, unit_price=4000.0
    )
    db_session.add_all([supplier, item])
    db_session.commit()
    return tenant, supplier, item


def test_purchase_order_defaults_to_draft(db_session):
    tenant, supplier, _ = _setup(db_session)

    po = PurchaseOrder(tenant_id=tenant.id, supplier_id=supplier.id)
    db_session.add(po)
    db_session.commit()

    stored = db_session.query(PurchaseOrder).one()
    assert stored.status == PurchaseOrderStatus.draft
    assert stored.received_at is None


def test_purchase_order_items_link_to_an_order(db_session):
    tenant, supplier, item = _setup(db_session)
    po = PurchaseOrder(tenant_id=tenant.id, supplier_id=supplier.id)
    db_session.add(po)
    db_session.commit()

    line = PurchaseOrderItem(
        tenant_id=tenant.id,
        purchase_order_id=po.id,
        inventory_item_id=item.id,
        quantity=20.0,
        unit_cost=2400.0,
    )
    db_session.add(line)
    db_session.commit()

    stored = db_session.query(PurchaseOrderItem).one()
    assert stored.purchase_order_id == po.id
    assert stored.quantity == 20.0
    assert stored.unit_cost == 2400.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purchase_order_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.purchase_order'`

- [ ] **Step 3: Write the models**

Create `backend/app/models/purchase_order.py`:

```python
import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class PurchaseOrderStatus(str, enum.Enum):
    draft = "draft"
    ordered = "ordered"
    received = "received"


class PurchaseOrder(Base, TenantScopedMixin):
    __tablename__ = "purchase_orders"

    supplier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        default=PurchaseOrderStatus.draft,
        server_default=PurchaseOrderStatus.draft.value,
        nullable=False,
    )
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Create `backend/app/models/purchase_order_item.py`:

```python
from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class PurchaseOrderItem(Base, TenantScopedMixin):
    __tablename__ = "purchase_order_items"

    purchase_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    inventory_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)
```

- [ ] **Step 4: Register the models**

Add `purchase_order` and `purchase_order_item` to the enumerated import on line 8 of `backend/alembic/env.py`, keeping alphabetical order. Leave `backend/app/models/__init__.py` empty — it is not the registration point.

```python
from app.models import asset, customer, inventory_item, job, job_labor_entry, job_part, platform_admin, purchase_order, purchase_order_item, supplier, tenant, user  # noqa: F401 -- registers models on Base.metadata
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purchase_order_model.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Generate and verify the migration**

Run: `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "create purchase orders tables"`

Confirm `purchase_orders` is created **before** `purchase_order_items` in `upgrade()`, and dropped in the reverse order in `downgrade()`. Then:

Run: `cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic downgrade -1 && .venv/bin/python -m alembic upgrade head`
Expected: all three succeed

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/purchase_order.py backend/app/models/purchase_order_item.py backend/app/models/__init__.py backend/alembic/versions/ backend/tests/test_purchase_order_model.py
git commit -m "feat(inventory): add PurchaseOrder and PurchaseOrderItem models and migration"
```

---

### Task 10: Purchase order create, list, and detail endpoints

**Files:**
- Create: `backend/app/schemas/purchase_order.py`
- Create: `backend/app/api/v1/purchase_orders.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_purchase_orders_api.py`

**Interfaces:**
- Consumes: `_get_supplier_or_404`, `_get_item_or_404`, `STAFF_ROLES`, `INVENTORY_READ_ROLES`
- Produces: `_get_po_or_404(db, tenant_id, po_id) -> PurchaseOrder` (Task 11 imports it); routes `POST/GET /purchase-orders`, `GET /purchase-orders/{po_id}`

A purchase order is created with its line items in one request. Every referenced inventory item is validated against the caller's tenant before anything is written.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_purchase_orders_api.py`:

```python
def _owner_token(client, platform_admin, email="owner-po@example.com", password="ownerpass123"):
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


def _supplier(client, token, name="Lanka Parts Ltd"):
    return client.post(
        "/api/v1/suppliers", json={"name": name}, headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]


def _item(client, token, sku="BP-001"):
    return client.post(
        "/api/v1/inventory-items",
        json={"sku": sku, "name": f"Item {sku}", "unit_cost": 2500.0, "unit_price": 4000.0},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def test_owner_can_create_a_purchase_order_with_line_items(client, platform_admin):
    token = _owner_token(client, platform_admin)
    headers = {"Authorization": f"Bearer {token}"}
    supplier_id = _supplier(client, token)
    item_id = _item(client, token)

    response = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "items": [{"inventory_item_id": item_id, "quantity": 20.0, "unit_cost": 2400.0}],
        },
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["received_at"] is None
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 20.0


def test_purchase_order_can_be_listed_and_fetched(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-po-list@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    supplier_id = _supplier(client, token)
    item_id = _item(client, token)
    po_id = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "items": [{"inventory_item_id": item_id, "quantity": 5.0, "unit_cost": 100.0}],
        },
        headers=headers,
    ).json()["id"]

    list_response = client.get("/api/v1/purchase-orders", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = client.get(f"/api/v1/purchase-orders/{po_id}", headers=headers)
    assert get_response.status_code == 200
    assert len(get_response.json()["items"]) == 1


def test_purchase_order_requires_at_least_one_line_item(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-po-empty@example.com")
    supplier_id = _supplier(client, token)

    response = client.post(
        "/api/v1/purchase-orders",
        json={"supplier_id": supplier_id, "items": []},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_supplier_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-po-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-po-b@example.com")
    foreign_supplier = _supplier(client, token_a)
    item_id = _item(client, token_b, sku="B-1")

    response = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": foreign_supplier,
            "items": [{"inventory_item_id": item_id, "quantity": 1.0, "unit_cost": 1.0}],
        },
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 404


def test_line_item_referencing_another_tenants_item_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-po-item-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-po-item-b@example.com")
    supplier_id = _supplier(client, token_b)
    foreign_item = _item(client, token_a, sku="A-1")

    response = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "items": [{"inventory_item_id": foreign_item, "quantity": 1.0, "unit_cost": 1.0}],
        },
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purchase_orders_api.py -v`
Expected: FAIL — routes do not exist

- [ ] **Step 3: Write the schemas**

Create `backend/app/schemas/purchase_order.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.purchase_order import PurchaseOrderStatus


class PurchaseOrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    purchase_order_id: str
    inventory_item_id: str
    quantity: float
    unit_cost: float


class PurchaseOrderItemCreate(BaseModel):
    inventory_item_id: str
    quantity: float = Field(gt=0)
    unit_cost: float = Field(ge=0)


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_id: str
    status: PurchaseOrderStatus
    received_at: datetime | None
    items: list[PurchaseOrderItemRead]


class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderRead]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 4: Add the relationship needed by `PurchaseOrderRead.items`**

In `backend/app/models/purchase_order.py`, add the import and the relationship so `from_attributes` can populate `items`:

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
```

```python
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem", lazy="selectin"
    )
```

- [ ] **Step 5: Write the router**

Create `backend/app/api/v1/purchase_orders.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.api.v1.inventory_items import INVENTORY_READ_ROLES, _get_item_or_404
from app.api.v1.suppliers import _get_supplier_or_404
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.user import User
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderListResponse,
    PurchaseOrderRead,
)

router = APIRouter()


def _get_po_or_404(db: Session, tenant_id: str, po_id: str) -> PurchaseOrder:
    po = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id)
        .first()
    )
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return po


@router.post("/purchase-orders", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrder:
    _get_supplier_or_404(db, current_user.tenant_id, payload.supplier_id)
    for line in payload.items:
        _get_item_or_404(db, current_user.tenant_id, line.inventory_item_id)

    po = PurchaseOrder(tenant_id=current_user.tenant_id, supplier_id=payload.supplier_id)
    db.add(po)
    db.flush()

    for line in payload.items:
        db.add(
            PurchaseOrderItem(
                tenant_id=current_user.tenant_id,
                purchase_order_id=po.id,
                inventory_item_id=line.inventory_item_id,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
            )
        )

    db.commit()
    db.refresh(po)
    return po


@router.get("/purchase-orders", response_model=PurchaseOrderListResponse)
def list_purchase_orders(
    current_user: Annotated[User, Depends(require_role(*INVENTORY_READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PurchaseOrderListResponse:
    query = db.query(PurchaseOrder).filter(PurchaseOrder.tenant_id == current_user.tenant_id)
    total = query.count()
    orders = query.offset((page - 1) * page_size).limit(page_size).all()
    return PurchaseOrderListResponse(items=orders, total=total, page=page, page_size=page_size)


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderRead)
def get_purchase_order(
    po_id: str,
    current_user: Annotated[User, Depends(require_role(*INVENTORY_READ_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrder:
    return _get_po_or_404(db, current_user.tenant_id, po_id)
```

- [ ] **Step 6: Mount the router**

In `backend/app/api/v1/router.py`, add `purchase_orders` to the import and mount it:

```python
api_router.include_router(purchase_orders.router, tags=["inventory"])
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purchase_orders_api.py -v`
Expected: PASS (5 tests)

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/purchase_order.py backend/app/api/v1/purchase_orders.py backend/app/api/v1/router.py backend/app/models/purchase_order.py backend/tests/test_purchase_orders_api.py
git commit -m "feat(inventory): add purchase order create, list, and detail endpoints"
```

---

### Task 11: Receive a purchase order (stock in)

**Files:**
- Modify: `backend/app/api/v1/purchase_orders.py`
- Test: `backend/tests/test_purchase_order_receive.py`

**Interfaces:**
- Consumes: `_get_po_or_404`, `PurchaseOrderStatus`, `InventoryItem`, `_now` from `app.db.base`
- Produces: `PATCH /purchase-orders/{po_id}/receive`

Receiving increments `quantity_on_hand` for every line item, sets `status = received` and `received_at`. It is allowed only from `draft` or `ordered`. Receiving an already-received order returns **409** — this is the guard that prevents double-incrementing stock.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_purchase_order_receive.py`:

```python
def _owner_token(client, platform_admin, email="owner-receive@example.com", password="ownerpass123"):
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


def _supplier(client, token):
    return client.post(
        "/api/v1/suppliers", json={"name": "Lanka Parts Ltd"}, headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]


def _item(client, token, sku="BP-001", quantity_on_hand=0.0):
    return client.post(
        "/api/v1/inventory-items",
        json={
            "sku": sku,
            "name": f"Item {sku}",
            "unit_cost": 2500.0,
            "unit_price": 4000.0,
            "quantity_on_hand": quantity_on_hand,
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def _po(client, token, supplier_id, lines):
    return client.post(
        "/api/v1/purchase-orders",
        json={"supplier_id": supplier_id, "items": lines},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def _on_hand(client, token, item_id):
    return client.get(
        f"/api/v1/inventory-items/{item_id}", headers={"Authorization": f"Bearer {token}"}
    ).json()["quantity_on_hand"]


def test_receiving_increments_stock_for_every_line(client, platform_admin):
    token = _owner_token(client, platform_admin)
    headers = {"Authorization": f"Bearer {token}"}
    supplier_id = _supplier(client, token)
    item_a = _item(client, token, sku="A-1", quantity_on_hand=2.0)
    item_b = _item(client, token, sku="B-1", quantity_on_hand=0.0)
    po_id = _po(
        client,
        token,
        supplier_id,
        [
            {"inventory_item_id": item_a, "quantity": 10.0, "unit_cost": 100.0},
            {"inventory_item_id": item_b, "quantity": 4.0, "unit_cost": 50.0},
        ],
    )

    response = client.patch(f"/api/v1/purchase-orders/{po_id}/receive", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "received"
    assert body["received_at"] is not None
    assert _on_hand(client, token, item_a) == 12.0
    assert _on_hand(client, token, item_b) == 4.0


def test_receiving_twice_returns_409_and_does_not_double_increment(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-receive-twice@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    supplier_id = _supplier(client, token)
    item_id = _item(client, token, quantity_on_hand=1.0)
    po_id = _po(client, token, supplier_id, [{"inventory_item_id": item_id, "quantity": 10.0, "unit_cost": 100.0}])

    assert client.patch(f"/api/v1/purchase-orders/{po_id}/receive", headers=headers).status_code == 200
    assert _on_hand(client, token, item_id) == 11.0

    second = client.patch(f"/api/v1/purchase-orders/{po_id}/receive", headers=headers)

    assert second.status_code == 409
    assert _on_hand(client, token, item_id) == 11.0


def test_receiving_another_tenants_purchase_order_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-receive-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-receive-b@example.com")
    supplier_id = _supplier(client, token_a)
    item_id = _item(client, token_a)
    po_id = _po(client, token_a, supplier_id, [{"inventory_item_id": item_id, "quantity": 1.0, "unit_cost": 1.0}])

    response = client.patch(
        f"/api/v1/purchase-orders/{po_id}/receive", headers={"Authorization": f"Bearer {token_b}"}
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purchase_order_receive.py -v`
Expected: FAIL — route does not exist

- [ ] **Step 3: Add the endpoint**

In `backend/app/api/v1/purchase_orders.py`, add these imports:

```python
from app.db.base import _now
from app.models.inventory_item import InventoryItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderStatus
```

Then append:

```python
@router.patch("/purchase-orders/{po_id}/receive", response_model=PurchaseOrderRead)
def receive_purchase_order(
    po_id: str,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrder:
    po = _get_po_or_404(db, current_user.tenant_id, po_id)
    if po.status == PurchaseOrderStatus.received:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Purchase order has already been received"
        )

    lines = (
        db.query(PurchaseOrderItem)
        .filter(
            PurchaseOrderItem.purchase_order_id == po.id,
            PurchaseOrderItem.tenant_id == current_user.tenant_id,
        )
        .all()
    )

    for line in lines:
        item = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.id == line.inventory_item_id,
                InventoryItem.tenant_id == current_user.tenant_id,
            )
            .with_for_update()
            .one()
        )
        item.quantity_on_hand = item.quantity_on_hand + line.quantity

    po.status = PurchaseOrderStatus.received
    po.received_at = _now()
    db.commit()
    db.refresh(po)
    return po
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purchase_order_receive.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/purchase_orders.py backend/tests/test_purchase_order_receive.py
git commit -m "feat(inventory): receive a purchase order and increment stock"
```

---

### Task 12: Purchase order status transitions

**Files:**
- Modify: `backend/app/api/v1/purchase_orders.py`
- Modify: `backend/app/schemas/purchase_order.py`
- Test: `backend/tests/test_purchase_order_status.py`

**Interfaces:**
- Consumes: `_get_po_or_404`, `PurchaseOrderStatus`
- Produces: `PATCH /purchase-orders/{po_id}/status`

Mirrors the job status machine in `app/api/v1/jobs.py`. `received` is reachable **only** through the receive endpoint, never through this one — that keeps the stock increment and the status change inseparable.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_purchase_order_status.py`:

```python
def _owner_token(client, platform_admin, email="owner-postatus@example.com", password="ownerpass123"):
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


def _draft_po(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    supplier_id = client.post("/api/v1/suppliers", json={"name": "S"}, headers=headers).json()["id"]
    item_id = client.post(
        "/api/v1/inventory-items",
        json={"sku": "S-1", "name": "Item", "unit_cost": 1.0, "unit_price": 2.0},
        headers=headers,
    ).json()["id"]
    return client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "items": [{"inventory_item_id": item_id, "quantity": 1.0, "unit_cost": 1.0}],
        },
        headers=headers,
    ).json()["id"]


def test_draft_can_move_to_ordered(client, platform_admin):
    token = _owner_token(client, platform_admin)
    headers = {"Authorization": f"Bearer {token}"}
    po_id = _draft_po(client, token)

    response = client.patch(
        f"/api/v1/purchase-orders/{po_id}/status", json={"status": "ordered"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ordered"


def test_status_endpoint_cannot_set_received(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-postatus-recv@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    po_id = _draft_po(client, token)

    response = client.patch(
        f"/api/v1/purchase-orders/{po_id}/status", json={"status": "received"}, headers=headers
    )

    assert response.status_code == 400


def test_received_order_cannot_change_status(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-postatus-after@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    po_id = _draft_po(client, token)
    client.patch(f"/api/v1/purchase-orders/{po_id}/receive", headers=headers)

    response = client.patch(
        f"/api/v1/purchase-orders/{po_id}/status", json={"status": "ordered"}, headers=headers
    )

    assert response.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purchase_order_status.py -v`
Expected: FAIL — route does not exist

- [ ] **Step 3: Add the update schema**

Append to `backend/app/schemas/purchase_order.py`:

```python
class PurchaseOrderStatusUpdate(BaseModel):
    status: PurchaseOrderStatus
```

- [ ] **Step 4: Add the endpoint**

Add `PurchaseOrderStatusUpdate` to the `app.schemas.purchase_order` import in `backend/app/api/v1/purchase_orders.py`, then append:

```python
_MANUAL_PO_TRANSITIONS: dict[PurchaseOrderStatus, set[PurchaseOrderStatus]] = {
    PurchaseOrderStatus.draft: {PurchaseOrderStatus.ordered},
    PurchaseOrderStatus.ordered: {PurchaseOrderStatus.draft},
    PurchaseOrderStatus.received: set(),
}


@router.patch("/purchase-orders/{po_id}/status", response_model=PurchaseOrderRead)
def update_purchase_order_status(
    po_id: str,
    payload: PurchaseOrderStatusUpdate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrder:
    po = _get_po_or_404(db, current_user.tenant_id, po_id)

    allowed = _MANUAL_PO_TRANSITIONS.get(po.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition purchase order from {po.status.value} to {payload.status.value}",
        )

    po.status = payload.status
    db.commit()
    db.refresh(po)
    return po
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purchase_order_status.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/purchase_orders.py backend/app/schemas/purchase_order.py backend/tests/test_purchase_order_status.py
git commit -m "feat(inventory): add purchase order status transitions"
```

---

### Task 13: Stock invariant and role integration tests

**Files:**
- Test: `backend/tests/test_inventory_stock_invariant.py`

**Interfaces:**
- Consumes: every endpoint built in Tasks 1-12. No production code changes in this task.

This task proves the plan's central invariant end-to-end: stock moves **only** by receiving a purchase order (in) and recording parts on a job (out), and the two compose correctly. It also verifies the role matrix from `docs/04-api-design.md` — technicians read inventory but never write it.

- [ ] **Step 1: Write the tests**

Create `backend/tests/test_inventory_stock_invariant.py`:

```python
def _admin_token(client, platform_admin):
    return client.post("/api/v1/admin/auth/login", json=platform_admin).json()["access_token"]


def _tenant_owner(client, platform_admin, email, password="ownerpass123"):
    admin_token = _admin_token(client, platform_admin)
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
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _technician_token(client, owner_token, email="tech-inv@example.com", password="techpass123"):
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": password, "role": "technician"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _item(client, token, sku="INV-1", quantity_on_hand=0.0):
    return client.post(
        "/api/v1/inventory-items",
        json={
            "sku": sku,
            "name": "Brake pad set",
            "unit_cost": 2500.0,
            "unit_price": 4000.0,
            "quantity_on_hand": quantity_on_hand,
            "reorder_threshold": 4.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def _on_hand(client, token, item_id):
    return client.get(
        f"/api/v1/inventory-items/{item_id}", headers={"Authorization": f"Bearer {token}"}
    ).json()["quantity_on_hand"]


def _job(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": "Nimal"}, headers=headers).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Corolla"},
        headers=headers,
    ).json()["id"]
    return client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Brake service"},
        headers=headers,
    ).json()["id"]


def test_receive_then_consume_leaves_correct_stock(client, platform_admin):
    token = _tenant_owner(client, platform_admin, "owner-invariant@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    item_id = _item(client, token, quantity_on_hand=0.0)
    supplier_id = client.post("/api/v1/suppliers", json={"name": "S"}, headers=headers).json()["id"]
    job_id = _job(client, token)

    po_id = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "items": [{"inventory_item_id": item_id, "quantity": 20.0, "unit_cost": 2400.0}],
        },
        headers=headers,
    ).json()["id"]
    client.patch(f"/api/v1/purchase-orders/{po_id}/receive", headers=headers)
    assert _on_hand(client, token, item_id) == 20.0

    client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 3.0},
        headers=headers,
    )
    client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 2.5},
        headers=headers,
    )

    assert _on_hand(client, token, item_id) == 14.5


def test_consumption_drives_an_item_into_the_low_stock_list(client, platform_admin):
    token = _tenant_owner(client, platform_admin, "owner-invariant-low@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    item_id = _item(client, token, quantity_on_hand=10.0)
    job_id = _job(client, token)

    assert client.get("/api/v1/inventory-items?low_stock=true", headers=headers).json()["total"] == 0

    client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 7.0},
        headers=headers,
    )

    low = client.get("/api/v1/inventory-items?low_stock=true", headers=headers).json()
    assert low["total"] == 1
    assert low["items"][0]["id"] == item_id


def test_technician_can_read_inventory_but_not_write_it(client, platform_admin):
    owner_token = _tenant_owner(client, platform_admin, "owner-invariant-role@example.com")
    tech_token = _technician_token(client, owner_token)
    tech_headers = {"Authorization": f"Bearer {tech_token}"}
    item_id = _item(client, owner_token, quantity_on_hand=5.0)

    assert client.get("/api/v1/inventory-items", headers=tech_headers).status_code == 200
    assert client.get(f"/api/v1/inventory-items/{item_id}", headers=tech_headers).status_code == 200

    create = client.post(
        "/api/v1/inventory-items",
        json={"sku": "TECH-1", "name": "Nope", "unit_cost": 1.0, "unit_price": 2.0},
        headers=tech_headers,
    )
    assert create.status_code == 403

    patch = client.patch(
        f"/api/v1/inventory-items/{item_id}", json={"unit_price": 1.0}, headers=tech_headers
    )
    assert patch.status_code == 403

    assert client.post("/api/v1/suppliers", json={"name": "Nope"}, headers=tech_headers).status_code == 403
```

- [ ] **Step 2: Run the tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_inventory_stock_invariant.py -v`
Expected: PASS (3 tests)

- [ ] **Step 3: Run the whole suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: all tests pass — 65 pre-existing plus every test added in Tasks 1-13

- [ ] **Step 4: Verify migrations apply from empty**

Run: `cd backend && rm -f torqbay.db && .venv/bin/python -m alembic upgrade head`
Expected: every migration applies cleanly in order with no error

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_inventory_stock_invariant.py
git commit -m "test(inventory): cover stock invariant and inventory role matrix"
```

---

## Deployment note

`docs/03-data-model.md` already documents every table in this plan. No documentation updates are required.

After merge, CI/CD deploys automatically (`.github/workflows/backend-ci-cd.yml` triggers on pushes to `main` touching `backend/**`) and runs `alembic upgrade head` against production MySQL. The six new tables are all additive — no existing table is altered — so the migration is safe to apply to live data.
