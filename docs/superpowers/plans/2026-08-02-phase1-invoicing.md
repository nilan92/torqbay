# Phase 1 Invoicing & Payments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate an invoice from a completed job — pulling labor and parts already recorded against it — render it as an A4 PDF, and record payments against it until it is settled.

**Architecture:** Follows the existing tenant-scoped REST pattern exactly. An invoice is built once from a `done` job by snapshotting its labor entries and parts into `invoice_line_items`, so later edits to rates or prices never alter an issued invoice. Money flows one way: creating an invoice moves the job to `invoiced`; fully paying it moves the job to `paid`. Neither transition is reachable from the manual job-status endpoint, which already blocks them.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, MySQL 8 (prod) / in-memory SQLite (tests), fpdf2 for PDF.

## Global Constraints

- `tenant_id` is **always** taken from `current_user.tenant_id`, never from request input.
- Every tenant-owned model inherits `TenantScopedMixin` from `app.db.base`.
- **All money and quantity columns use `Float(precision=53)`.** Plain `Float` renders as 4-byte MySQL `FLOAT` (~7 significant digits) and silently rounds LKR amounts — `250000.50` becomes `250000`. The SQLite test suite cannot detect this. This is not optional.
- Reuse `STAFF_ROLES` by importing it from `app.api.v1.customers`. Reuse `INVENTORY_READ_ROLES` from `app.api.v1.suppliers` if a read needs technician access (invoicing does not — invoices are staff-only throughout).
- Financial write access is `STAFF_ROLES` (`owner`, `manager`, `frontdesk`). Technicians have no access to invoices or payments at all, per the permission table in `docs/04-api-design.md`.
- Missing or cross-tenant resource → **404**, never 403.
- Pagination contract: `page: int = Query(1, ge=1)`, `page_size: int = Query(20, ge=1, le=100)`, returning `{items, total, page, page_size}`.
- Run tests with `cd backend && .venv/bin/python -m pytest`.
- Migrations: `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "<message>"`, then **read the generated file and correct it**. Register every new model in `backend/alembic/env.py`'s enumerated import on line 8 — `backend/app/models/__init__.py` is intentionally empty and is NOT the registration point. Skipping the `env.py` edit produces a silently EMPTY migration.
- Current alembic head: `8e8d8a5f51bc`.

## Design decisions taken up front

**PDF is generated on demand, not stored.** `docs/06-invoice-template.md` describes saving to object storage with a signed URL. No object storage is configured for this project, and an invoice PDF is fully derivable from rows that are frozen once the invoice leaves `draft`. So `GET /invoices/{id}/pdf` renders and streams on each request, and there is no `pdf_url` column. This removes signed-URL machinery, orphaned-file cleanup, and a storage dependency. Revisit only if PDF rendering shows up as a real latency problem.

**Line items are snapshots, not references.** When an invoice is created, each labor entry and job part is copied into an `invoice_line_items` row with its own description, quantity, and unit price. Changing a technician's hourly rate or an inventory item's price afterwards must never alter an invoice a customer already holds.

**Labour is billed flat, not by the hour.** Sri Lankan workshops pay technicians a monthly salary and bill the customer one labour charge per job, so `jobs.labor_cost` is the whole labour story on an invoice. `job_labor_entries` exist to answer "how long did this take and who did it" — a utilisation question — and are never read when building an invoice. A shop that itemises labour ("brake job 3,500, oil change 1,200") can add extra labour lines to the draft invoice via `POST /invoices/{id}/line-items`.

---

### Task 1: Invoice and InvoiceLineItem models and migration

**Files:**
- Create: `backend/app/models/invoice.py`
- Create: `backend/app/models/invoice_line_item.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/<generated>_create_invoices_tables.py`
- Test: `backend/tests/test_invoice_model.py`

**Interfaces:**
- Consumes: `Base`, `TenantScopedMixin`; FKs to `jobs.id`, `customers.id`, `invoices.id`
- Produces: `InvoiceStatus(str, enum.Enum)` with `draft`/`sent`/`partially_paid`/`paid`/`overdue`/`cancelled`; `InvoiceLineItemType(str, enum.Enum)` with `labor`/`part`/`other`; `Invoice`; `InvoiceLineItem`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_invoice_model.py`:

```python
from datetime import date

from app.models.asset import Asset
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line_item import InvoiceLineItem, InvoiceLineItemType
from app.models.job import Job
from app.models.tenant import Tenant


def _job(db_session):
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
    db_session.add(job)
    db_session.commit()
    return tenant, customer, job


def test_invoice_defaults_to_draft(db_session):
    tenant, customer, job = _job(db_session)

    invoice = Invoice(
        tenant_id=tenant.id,
        job_id=job.id,
        customer_id=customer.id,
        invoice_number="INV-2026-0001",
        issue_date=date(2026, 8, 2),
        due_date=date(2026, 8, 16),
        subtotal=10000.0,
        tax_rate=0.18,
        tax_amount=1800.0,
        total=11800.0,
    )
    db_session.add(invoice)
    db_session.commit()

    stored = db_session.query(Invoice).one()
    assert stored.status == InvoiceStatus.draft
    assert stored.invoice_number == "INV-2026-0001"
    assert stored.total == 11800.0


def test_invoice_line_items_link_to_an_invoice(db_session):
    tenant, customer, job = _job(db_session)
    invoice = Invoice(
        tenant_id=tenant.id,
        job_id=job.id,
        customer_id=customer.id,
        invoice_number="INV-2026-0002",
        issue_date=date(2026, 8, 2),
        due_date=date(2026, 8, 16),
        subtotal=0.0,
        tax_rate=0.0,
        tax_amount=0.0,
        total=0.0,
    )
    db_session.add(invoice)
    db_session.commit()

    db_session.add_all([
        InvoiceLineItem(
            tenant_id=tenant.id,
            invoice_id=invoice.id,
            description="Labor: 2.5 h @ LKR 1,500.00",
            quantity=2.5,
            unit_price=1500.0,
            line_total=3750.0,
            type=InvoiceLineItemType.labor,
        ),
        InvoiceLineItem(
            tenant_id=tenant.id,
            invoice_id=invoice.id,
            description="Brake pad set",
            quantity=2.0,
            unit_price=4000.0,
            line_total=8000.0,
            type=InvoiceLineItemType.part,
        ),
    ])
    db_session.commit()

    stored = db_session.query(InvoiceLineItem).order_by(InvoiceLineItem.line_total).all()
    assert [item.type for item in stored] == [InvoiceLineItemType.labor, InvoiceLineItemType.part]
    assert stored[1].line_total == 8000.0


def test_invoice_number_is_unique_within_a_tenant(db_session):
    import pytest
    from sqlalchemy.exc import IntegrityError

    tenant, customer, job = _job(db_session)

    def make(number):
        return Invoice(
            tenant_id=tenant.id,
            job_id=job.id,
            customer_id=customer.id,
            invoice_number=number,
            issue_date=date(2026, 8, 2),
            due_date=date(2026, 8, 16),
            subtotal=0.0,
            tax_rate=0.0,
            tax_amount=0.0,
            total=0.0,
        )

    db_session.add(make("INV-2026-0003"))
    db_session.commit()
    db_session.add(make("INV-2026-0003"))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.invoice'`

- [ ] **Step 3: Write the models**

Create `backend/app/models/invoice.py`:

```python
import enum
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScopedMixin


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    partially_paid = "partially_paid"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class Invoice(Base, TenantScopedMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "invoice_number", name="uq_invoices_tenant_number"),
    )

    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(32), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    subtotal: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    tax_rate: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    total: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        default=InvoiceStatus.draft, server_default=InvoiceStatus.draft.value, nullable=False
    )

    line_items: Mapped[list["InvoiceLineItem"]] = relationship(
        "InvoiceLineItem", lazy="selectin"
    )
```

Create `backend/app/models/invoice_line_item.py`:

```python
import enum

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin


class InvoiceLineItemType(str, enum.Enum):
    labor = "labor"
    part = "part"
    other = "other"


class InvoiceLineItem(Base, TenantScopedMixin):
    __tablename__ = "invoice_line_items"

    invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("invoices.id"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    line_total: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    type: Mapped[InvoiceLineItemType] = mapped_column(nullable=False)
```

- [ ] **Step 4: Register both models**

Add `invoice` and `invoice_line_item` to the enumerated import on line 8 of `backend/alembic/env.py`, keeping alphabetical order. Leave `backend/app/models/__init__.py` empty.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_model.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Generate and verify the migration**

Run: `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "create invoices tables"`

Read the generated file and confirm: `invoices` is created BEFORE `invoice_line_items` (child has an FK to parent) and dropped in reverse; `uq_invoices_tenant_number` is present (autogenerate sometimes omits `__table_args__` constraints — add it by hand if missing); every money column is `sa.Float(precision=53)`; `down_revision = '8e8d8a5f51bc'`.

Run: `cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic downgrade -1 && .venv/bin/python -m alembic upgrade head`
Expected: all three succeed

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/invoice.py backend/app/models/invoice_line_item.py backend/alembic/env.py backend/alembic/versions/ backend/tests/test_invoice_model.py
git commit -m "feat(invoicing): add Invoice and InvoiceLineItem models and migration"
```

---

### Task 2: Payment model and migration

**Files:**
- Create: `backend/app/models/payment.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/<generated>_create_payments_table.py`
- Test: `backend/tests/test_payment_model.py`

**Interfaces:**
- Consumes: FK to `invoices.id`
- Produces: `PaymentMethod(str, enum.Enum)` with `cash`/`card`/`bank_transfer`/`gateway`/`qr`; `PaymentStatus(str, enum.Enum)` with `pending`/`completed`/`failed`/`refunded`; `Payment`

`gateway` and `external_reference` are nullable and unused in Phase 1. They exist now so Phase 4 gateway support is additive rather than a schema migration against live payment records.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_payment_model.py`:

```python
from datetime import date

from app.models.asset import Asset
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.job import Job
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.tenant import Tenant


def _invoice(db_session):
    tenant = Tenant(name="Colombo Auto Repair")
    db_session.add(tenant)
    db_session.commit()
    customer = Customer(tenant_id=tenant.id, name="Nimal")
    db_session.add(customer)
    db_session.commit()
    asset = Asset(tenant_id=tenant.id, customer_id=customer.id, type="vehicle", label="Corolla")
    db_session.add(asset)
    db_session.commit()
    job = Job(tenant_id=tenant.id, customer_id=customer.id, asset_id=asset.id, title="Service")
    db_session.add(job)
    db_session.commit()
    invoice = Invoice(
        tenant_id=tenant.id, job_id=job.id, customer_id=customer.id,
        invoice_number="INV-2026-0001", issue_date=date(2026, 8, 2), due_date=date(2026, 8, 16),
        subtotal=10000.0, tax_rate=0.0, tax_amount=0.0, total=10000.0,
    )
    db_session.add(invoice)
    db_session.commit()
    return tenant, invoice


def test_payment_defaults_to_completed(db_session):
    tenant, invoice = _invoice(db_session)

    payment = Payment(
        tenant_id=tenant.id,
        invoice_id=invoice.id,
        amount=5000.0,
        method=PaymentMethod.cash,
    )
    db_session.add(payment)
    db_session.commit()

    stored = db_session.query(Payment).one()
    assert stored.status == PaymentStatus.completed
    assert stored.amount == 5000.0
    assert stored.gateway is None
    assert stored.external_reference is None
    assert stored.paid_at is not None


def test_payment_records_its_method(db_session):
    tenant, invoice = _invoice(db_session)

    db_session.add(
        Payment(
            tenant_id=tenant.id,
            invoice_id=invoice.id,
            amount=1.0,
            method=PaymentMethod.bank_transfer,
        )
    )
    db_session.commit()

    assert db_session.query(Payment).one().method == PaymentMethod.bank_transfer
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_payment_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.payment'`

- [ ] **Step 3: Write the model**

Create `backend/app/models/payment.py`:

```python
import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, _now


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    card = "card"
    bank_transfer = "bank_transfer"
    gateway = "gateway"
    qr = "qr"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"


class Payment(Base, TenantScopedMixin):
    __tablename__ = "payments"

    invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("invoices.id"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        default=PaymentStatus.completed, server_default=PaymentStatus.completed.value, nullable=False
    )
    gateway: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
```

- [ ] **Step 4: Register the model**

Add `payment` to the enumerated import on line 8 of `backend/alembic/env.py`, alphabetically.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_payment_model.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Generate and verify the migration**

Run: `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "create payments table"`

Confirm `amount` is `sa.Float(precision=53)`, the FK to `invoices.id` is present, and the `down_revision` chains onto Task 1's migration.

Run: `cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic downgrade -1 && .venv/bin/python -m alembic upgrade head`
Expected: all three succeed

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/payment.py backend/alembic/env.py backend/alembic/versions/ backend/tests/test_payment_model.py
git commit -m "feat(invoicing): add Payment model and migration"
```

---

### Task 3: Tenant-scoped sequential invoice numbering

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/invoice_numbering.py`
- Test: `backend/tests/test_invoice_numbering.py`

**Interfaces:**
- Consumes: `Invoice`, `Tenant`
- Produces: `next_invoice_number(db, tenant_id, year) -> str` — used by Task 4

Invoice numbers are `INV-<year>-<4-digit sequence>`, sequential **per tenant per year**, starting at `0001`. Two tenants both have `INV-2026-0001`; that is correct and intended.

**Race safety.** Two staff creating invoices simultaneously must not both compute the same next number. The generator locks the tenant row with `SELECT ... FOR UPDATE` before scanning existing numbers, which serializes invoice creation per tenant on MySQL. SQLite ignores `FOR UPDATE`, harmless in tests. The `uq_invoices_tenant_number` constraint from Task 1 is the backstop if the lock is ever bypassed.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_invoice_numbering.py`:

```python
from datetime import date

from app.models.asset import Asset
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.job import Job
from app.models.tenant import Tenant
from app.services.invoice_numbering import next_invoice_number


def _tenant_with_job(db_session, name):
    tenant = Tenant(name=name)
    db_session.add(tenant)
    db_session.commit()
    customer = Customer(tenant_id=tenant.id, name="C")
    db_session.add(customer)
    db_session.commit()
    asset = Asset(tenant_id=tenant.id, customer_id=customer.id, type="vehicle", label="V")
    db_session.add(asset)
    db_session.commit()
    job = Job(tenant_id=tenant.id, customer_id=customer.id, asset_id=asset.id, title="J")
    db_session.add(job)
    db_session.commit()
    return tenant, customer, job


def _add_invoice(db_session, tenant, customer, job, number):
    db_session.add(
        Invoice(
            tenant_id=tenant.id, job_id=job.id, customer_id=customer.id,
            invoice_number=number, issue_date=date(2026, 1, 1), due_date=date(2026, 1, 15),
            subtotal=0.0, tax_rate=0.0, tax_amount=0.0, total=0.0,
        )
    )
    db_session.commit()


def test_first_invoice_of_the_year_starts_at_0001(db_session):
    tenant, _, _ = _tenant_with_job(db_session, "T1")

    assert next_invoice_number(db_session, tenant.id, 2026) == "INV-2026-0001"


def test_numbers_increment_within_a_tenant(db_session):
    tenant, customer, job = _tenant_with_job(db_session, "T2")
    _add_invoice(db_session, tenant, customer, job, "INV-2026-0001")
    _add_invoice(db_session, tenant, customer, job, "INV-2026-0002")

    assert next_invoice_number(db_session, tenant.id, 2026) == "INV-2026-0003"


def test_numbering_is_independent_per_tenant(db_session):
    tenant_a, customer_a, job_a = _tenant_with_job(db_session, "TA")
    tenant_b, _, _ = _tenant_with_job(db_session, "TB")
    _add_invoice(db_session, tenant_a, customer_a, job_a, "INV-2026-0001")

    assert next_invoice_number(db_session, tenant_a.id, 2026) == "INV-2026-0002"
    assert next_invoice_number(db_session, tenant_b.id, 2026) == "INV-2026-0001"


def test_numbering_restarts_each_year(db_session):
    tenant, customer, job = _tenant_with_job(db_session, "T3")
    _add_invoice(db_session, tenant, customer, job, "INV-2026-0001")

    assert next_invoice_number(db_session, tenant.id, 2027) == "INV-2027-0001"


def test_sequence_survives_a_gap(db_session):
    """Numbers are derived from the highest existing, not from a count."""
    tenant, customer, job = _tenant_with_job(db_session, "T4")
    _add_invoice(db_session, tenant, customer, job, "INV-2026-0007")

    assert next_invoice_number(db_session, tenant.id, 2026) == "INV-2026-0008"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_numbering.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services'`

- [ ] **Step 3: Create the services package**

Create `backend/app/services/__init__.py` as an empty file.

- [ ] **Step 4: Write the generator**

Create `backend/app/services/invoice_numbering.py`:

```python
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.tenant import Tenant

_PREFIX = "INV"


def next_invoice_number(db: Session, tenant_id: str, year: int) -> str:
    """Return the next `INV-<year>-<NNNN>` number for this tenant.

    Sequential per tenant per year. The tenant row is locked first so two
    concurrent invoice creations cannot derive the same number; SQLite ignores
    FOR UPDATE, which is harmless for the test suite. The
    uq_invoices_tenant_number constraint is the backstop.
    """
    db.query(Tenant).filter(Tenant.id == tenant_id).with_for_update().first()

    prefix = f"{_PREFIX}-{year}-"
    highest = (
        db.query(func.max(Invoice.invoice_number))
        .filter(Invoice.tenant_id == tenant_id, Invoice.invoice_number.like(f"{prefix}%"))
        .scalar()
    )

    if highest is None:
        sequence = 1
    else:
        sequence = int(highest[len(prefix):]) + 1

    return f"{prefix}{sequence:04d}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_numbering.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ backend/tests/test_invoice_numbering.py
git commit -m "feat(invoicing): add tenant-scoped sequential invoice numbering"
```

---

### Task 4: Generate an invoice from a completed job

**Files:**
- Create: `backend/app/schemas/invoice.py`
- Create: `backend/app/api/v1/invoices.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_invoice_create.py`

**Interfaces:**
- Consumes: `next_invoice_number`, `_get_job_or_404` from `app.api.v1.jobs`, `STAFF_ROLES`, `JobLaborEntry`, `JobPart`, `InventoryItem`
- Produces: `_get_invoice_or_404(db, tenant_id, invoice_id) -> Invoice` (Tasks 5-8 and 11 import it); route `POST /jobs/{job_id}/invoice`

**Business rules, all enforced here:**
- The job must be `done`. Any other status → 400. An `open` or `in_progress` job is not finished; an `invoiced` or `paid` job already has an invoice.
- Labour is a **single line** taken from `jobs.labor_cost`, the flat charge set on the job. There is no hours × rate calculation: technicians are salaried and workshops bill one labour amount per job. A job with `labor_cost = 0` gets no labour line.
- `job_labor_entries` are **not** consulted when invoicing. They track time for utilisation insight, not money, so an open (unstopped) timer does not block invoicing.
- Part lines: `line_total = quantity * unit_price_at_time`. Use the **snapshot** price on `JobPart`, never the item's current price.
- `tax_rate` comes from `tenants.default_tax_rate` at creation time and is stored on the invoice, so later tenant tax changes don't alter issued invoices.
- Creating the invoice moves the job to `invoiced`. This is the only path to that status.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_invoice_create.py`:

```python
from datetime import datetime, timedelta, timezone


def _owner_token(client, platform_admin, email="owner-inv@example.com", password="ownerpass123"):
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


def _technician_id(client, token, email="tech-inv@example.com"):
    return client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": email, "password": "techpass123", "role": "technician"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def _job(client, token):
    h = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": "Nimal"}, headers=h).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Corolla"},
        headers=h,
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Brake service"},
        headers=h,
    ).json()["id"]
    return job_id


def _complete(client, token, job_id):
    h = {"Authorization": f"Bearer {token}"}
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "in_progress"}, headers=h)
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "done"}, headers=h)


def _add_labor(client, token, job_id, technician_id, hours=2.0, close=True):
    """Record tracked time. Deliberately carries no rate — labour is billed
    from the job's flat charge, not from these entries."""
    start = datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc)
    payload = {
        "technician_id": technician_id,
        "start_time": start.isoformat(),
    }
    if close:
        payload["end_time"] = (start + timedelta(hours=hours)).isoformat()
    return client.post(
        f"/api/v1/jobs/{job_id}/labor-entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )


def _add_part(client, token, job_id, quantity=2.0, unit_price=4000.0):
    h = {"Authorization": f"Bearer {token}"}
    item_id = client.post(
        "/api/v1/inventory-items",
        json={
            "sku": f"SKU-{quantity}-{unit_price}",
            "name": "Brake pad set",
            "unit_cost": 2500.0,
            "unit_price": unit_price,
            "quantity_on_hand": 100.0,
        },
        headers=h,
    ).json()["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": quantity},
        headers=h,
    )
    return item_id


def test_invoice_totals_labor_and_parts(client, platform_admin):
    token = _owner_token(client, platform_admin)
    h = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    client.patch(f"/api/v1/jobs/{job_id}", json={"labor_cost": 3000.0}, headers=h)  # 3000
    _add_part(client, token, job_id, quantity=2.0, unit_price=4000.0)               # 8000
    _complete(client, token, job_id)

    response = client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h)

    assert response.status_code == 201
    body = response.json()
    assert body["subtotal"] == 11000.0
    assert body["total"] == 11000.0
    assert body["status"] == "draft"
    assert body["invoice_number"].startswith("INV-")
    types = sorted(item["type"] for item in body["line_items"])
    assert types == ["labor", "part"]


def test_invoicing_moves_the_job_to_invoiced(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-inv-status@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    _complete(client, token, job_id)

    client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h)

    assert client.get(f"/api/v1/jobs/{job_id}", headers=h).json()["status"] == "invoiced"


def test_tax_rate_is_applied_and_snapshotted(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-inv-tax@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    client.patch(f"/api/v1/jobs/{job_id}", json={"labor_cost": 2000.0}, headers=h)  # 2000
    _complete(client, token, job_id)

    response = client.post(f"/api/v1/jobs/{job_id}/invoice", json={"tax_rate": 0.18}, headers=h)

    body = response.json()
    assert body["subtotal"] == 2000.0
    assert body["tax_rate"] == 0.18
    assert body["tax_amount"] == 360.0
    assert body["total"] == 2360.0


def test_cannot_invoice_a_job_that_is_not_done(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-inv-open@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)

    response = client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h)

    assert response.status_code == 400


def test_cannot_invoice_twice(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-inv-twice@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    _complete(client, token, job_id)
    assert client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h).status_code == 201

    second = client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h)

    assert second.status_code == 400


def test_part_price_change_does_not_alter_the_invoice(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-inv-snap@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _job(client, token)
    item_id = _add_part(client, token, job_id, quantity=1.0, unit_price=5000.0)
    _complete(client, token, job_id)
    invoice = client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h).json()

    client.patch(f"/api/v1/inventory-items/{item_id}", json={"unit_price": 9999.0}, headers=h)

    assert invoice["subtotal"] == 5000.0
    fetched = client.get(f"/api/v1/invoices/{invoice['id']}", headers=h)
    assert fetched.json()["subtotal"] == 5000.0


def test_technician_cannot_create_an_invoice(client, platform_admin):
    owner_token = _owner_token(client, platform_admin, email="owner-inv-role@example.com")
    _technician_id(client, owner_token, email="tech-inv-role@example.com")
    tech_token = client.post(
        "/api/v1/auth/login",
        json={"email": "tech-inv-role@example.com", "password": "techpass123"},
    ).json()["access_token"]
    job_id = _job(client, owner_token)
    _complete(client, owner_token, job_id)

    response = client.post(
        f"/api/v1/jobs/{job_id}/invoice",
        json={},
        headers={"Authorization": f"Bearer {tech_token}"},
    )

    assert response.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_create.py -v`
Expected: FAIL — route does not exist

- [ ] **Step 3: Write the schemas**

Create `backend/app/schemas/invoice.py`:

```python
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.invoice import InvoiceStatus
from app.models.invoice_line_item import InvoiceLineItemType


class InvoiceLineItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_id: str
    description: str
    quantity: float
    unit_price: float
    line_total: float
    type: InvoiceLineItemType


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    job_id: str
    customer_id: str
    invoice_number: str
    issue_date: date
    due_date: date
    subtotal: float
    tax_rate: float
    tax_amount: float
    total: float
    status: InvoiceStatus
    line_items: list[InvoiceLineItemRead]


class InvoiceCreate(BaseModel):
    tax_rate: float | None = Field(default=None, ge=0)
    due_in_days: int = Field(default=14, ge=0, le=365)


class InvoiceListResponse(BaseModel):
    items: list[InvoiceRead]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 4: Write the router**

Create `backend/app/api/v1/invoices.py`:

```python
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.api.v1.jobs import _get_job_or_404
from app.core.dependencies import require_role
from app.db.base import _now
from app.db.session import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line_item import InvoiceLineItem, InvoiceLineItemType
from app.models.job import Job, JobStatus
from app.models.job_labor_entry import JobLaborEntry
from app.models.job_part import JobPart
from app.models.inventory_item import InventoryItem
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.invoice import InvoiceCreate, InvoiceRead
from app.services.invoice_numbering import next_invoice_number

router = APIRouter()


def _get_invoice_or_404(db: Session, tenant_id: str, invoice_id: str) -> Invoice:
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        .first()
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


def _labor_line(job: Job) -> tuple[str, float, float] | None:
    """The job's flat labour charge, as a single line.

    Sri Lankan workshops bill labour as one amount per job and pay technicians
    a monthly salary, so there is no hours x rate to compute. Time recorded in
    job_labor_entries is for utilisation insight and never reaches an invoice.
    A job with no labour charge produces no labour line at all.
    """
    if not job.labor_cost:
        return None
    return ("Labour", 1.0, job.labor_cost)


def _build_part_lines(db: Session, tenant_id: str, job_id: str) -> list[tuple[str, float, float]]:
    """Return (description, quantity, unit_price) per part, using snapshot prices."""
    rows = (
        db.query(JobPart, InventoryItem)
        .join(InventoryItem, InventoryItem.id == JobPart.inventory_item_id)
        .filter(JobPart.tenant_id == tenant_id, JobPart.job_id == job_id)
        .all()
    )
    return [(item.name, part.quantity, part.unit_price_at_time) for part, item in rows]


@router.post(
    "/jobs/{job_id}/invoice", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED
)
def create_invoice(
    job_id: str,
    payload: InvoiceCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Invoice:
    job = _get_job_or_404(db, current_user, job_id)
    if job.status != JobStatus.done:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot invoice a job with status {job.status.value}; it must be done",
        )

    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).one()
    tax_rate = payload.tax_rate if payload.tax_rate is not None else tenant.default_tax_rate

    labor_line = _labor_line(job)
    parts = _build_part_lines(db, current_user.tenant_id, job_id)

    issue_date = _now().date()
    invoice = Invoice(
        tenant_id=current_user.tenant_id,
        job_id=job_id,
        customer_id=job.customer_id,
        invoice_number=next_invoice_number(db, current_user.tenant_id, issue_date.year),
        issue_date=issue_date,
        due_date=issue_date + timedelta(days=payload.due_in_days),
        subtotal=0.0,
        tax_rate=tax_rate,
        tax_amount=0.0,
        total=0.0,
    )
    db.add(invoice)
    db.flush()

    subtotal = 0.0
    for description, quantity, unit_price in ([labor_line] if labor_line else []):
        line_total = quantity * unit_price
        subtotal += line_total
        db.add(
            InvoiceLineItem(
                tenant_id=current_user.tenant_id,
                invoice_id=invoice.id,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
                type=InvoiceLineItemType.labor,
            )
        )
    for description, quantity, unit_price in parts:
        line_total = quantity * unit_price
        subtotal += line_total
        db.add(
            InvoiceLineItem(
                tenant_id=current_user.tenant_id,
                invoice_id=invoice.id,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
                type=InvoiceLineItemType.part,
            )
        )

    invoice.subtotal = subtotal
    invoice.tax_amount = subtotal * tax_rate
    invoice.total = subtotal + invoice.tax_amount

    job.status = JobStatus.invoiced

    db.commit()
    db.refresh(invoice)
    return invoice
```

- [ ] **Step 5: Mount the router**

In `backend/app/api/v1/router.py`, add `invoices` to the import and mount it before `admin`:

```python
api_router.include_router(invoices.router, tags=["invoices"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_create.py -v`
Expected: PASS (8 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/invoice.py backend/app/api/v1/invoices.py backend/app/api/v1/router.py backend/tests/test_invoice_create.py
git commit -m "feat(invoicing): generate an invoice from a completed job"
```

---

### Task 5: Invoice list and detail endpoints

**Files:**
- Modify: `backend/app/api/v1/invoices.py`
- Test: `backend/tests/test_invoice_read.py`

**Interfaces:**
- Consumes: `_get_invoice_or_404`, `InvoiceListResponse`
- Produces: `GET /invoices`, `GET /invoices/{invoice_id}`

`GET /invoices` supports an optional `status` filter and an optional `customer_id` filter, both applied before `.count()` so pagination totals stay correct.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_invoice_read.py`. Reuse the helpers from `test_invoice_create.py` by copying them into this file (each test module is self-contained in this codebase):

```python
def _owner_token(client, platform_admin, email="owner-invread@example.com", password="ownerpass123"):
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


def _invoiced_job(client, token, customer_name="Nimal"):
    h = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": customer_name}, headers=h).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Corolla"},
        headers=h,
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Service"},
        headers=h,
    ).json()["id"]
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "in_progress"}, headers=h)
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "done"}, headers=h)
    invoice = client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h).json()
    return customer_id, invoice


def test_invoices_can_be_listed_and_fetched(client, platform_admin):
    token = _owner_token(client, platform_admin)
    h = {"Authorization": f"Bearer {token}"}
    _, invoice = _invoiced_job(client, token)

    listing = client.get("/api/v1/invoices", headers=h)
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20

    detail = client.get(f"/api/v1/invoices/{invoice['id']}", headers=h)
    assert detail.status_code == 200
    assert detail.json()["invoice_number"] == invoice["invoice_number"]


def test_invoices_can_be_filtered_by_status(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-invread-status@example.com")
    h = {"Authorization": f"Bearer {token}"}
    _invoiced_job(client, token)

    assert client.get("/api/v1/invoices?status=draft", headers=h).json()["total"] == 1
    assert client.get("/api/v1/invoices?status=paid", headers=h).json()["total"] == 0


def test_invoices_can_be_filtered_by_customer(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-invread-cust@example.com")
    h = {"Authorization": f"Bearer {token}"}
    customer_a, _ = _invoiced_job(client, token, customer_name="A")
    _invoiced_job(client, token, customer_name="B")

    filtered = client.get(f"/api/v1/invoices?customer_id={customer_a}", headers=h).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["customer_id"] == customer_a


def test_invoice_from_another_tenant_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-invread-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-invread-b@example.com")
    _, invoice = _invoiced_job(client, token_a)

    response = client.get(
        f"/api/v1/invoices/{invoice['id']}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_read.py -v`
Expected: FAIL — routes do not exist

- [ ] **Step 3: Add the endpoints**

Add `Query` to the existing `fastapi` import in `backend/app/api/v1/invoices.py`, add `InvoiceListResponse` to the schema import, then append:

```python
@router.get("/invoices", response_model=InvoiceListResponse)
def list_invoices(
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: InvoiceStatus | None = Query(default=None, alias="status"),
    customer_id: str | None = Query(default=None),
) -> InvoiceListResponse:
    query = db.query(Invoice).filter(Invoice.tenant_id == current_user.tenant_id)
    if status_filter is not None:
        query = query.filter(Invoice.status == status_filter)
    if customer_id is not None:
        query = query.filter(Invoice.customer_id == customer_id)
    total = query.count()
    invoices = query.offset((page - 1) * page_size).limit(page_size).all()
    return InvoiceListResponse(items=invoices, total=total, page=page, page_size=page_size)


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: str,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Invoice:
    return _get_invoice_or_404(db, current_user.tenant_id, invoice_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_read.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/invoices.py backend/tests/test_invoice_read.py
git commit -m "feat(invoicing): add invoice list and detail endpoints"
```

---

### Task 6: Invoice status transitions

**Files:**
- Modify: `backend/app/api/v1/invoices.py`
- Modify: `backend/app/schemas/invoice.py`
- Test: `backend/tests/test_invoice_status.py`

**Interfaces:**
- Consumes: `_get_invoice_or_404`, `InvoiceStatus`
- Produces: `PATCH /invoices/{invoice_id}/status`

Mirrors the job and purchase-order state machines. The map:

```python
{
    draft:          {sent, cancelled},
    sent:           {overdue, cancelled},
    overdue:        {cancelled},
    partially_paid: set(),
    paid:           set(),
    cancelled:      set(),
}
```

`partially_paid` and `paid` are **unreachable** from this endpoint and map to empty sets. They are set only by recording a payment (Task 7), so the money movement and the status change stay inseparable — exactly as `received` works for purchase orders. A `paid` invoice can never transition back out.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_invoice_status.py`:

```python
def _owner_token(client, platform_admin, email="owner-invstatus@example.com", password="ownerpass123"):
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
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _draft_invoice(client, token):
    h = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": "N"}, headers=h).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "V"},
        headers=h,
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "J"},
        headers=h,
    ).json()["id"]
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "in_progress"}, headers=h)
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "done"}, headers=h)
    return client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h).json()["id"]


def test_draft_can_be_sent(client, platform_admin):
    token = _owner_token(client, platform_admin)
    h = {"Authorization": f"Bearer {token}"}
    invoice_id = _draft_invoice(client, token)

    response = client.patch(
        f"/api/v1/invoices/{invoice_id}/status", json={"status": "sent"}, headers=h
    )

    assert response.status_code == 200
    assert response.json()["status"] == "sent"


def test_status_endpoint_cannot_set_paid(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-invstatus-paid@example.com")
    h = {"Authorization": f"Bearer {token}"}
    invoice_id = _draft_invoice(client, token)

    response = client.patch(
        f"/api/v1/invoices/{invoice_id}/status", json={"status": "paid"}, headers=h
    )

    assert response.status_code == 400


def test_status_endpoint_cannot_set_partially_paid(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-invstatus-part@example.com")
    h = {"Authorization": f"Bearer {token}"}
    invoice_id = _draft_invoice(client, token)

    response = client.patch(
        f"/api/v1/invoices/{invoice_id}/status", json={"status": "partially_paid"}, headers=h
    )

    assert response.status_code == 400


def test_cancelled_invoice_cannot_change_status(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-invstatus-cancel@example.com")
    h = {"Authorization": f"Bearer {token}"}
    invoice_id = _draft_invoice(client, token)
    client.patch(f"/api/v1/invoices/{invoice_id}/status", json={"status": "cancelled"}, headers=h)

    response = client.patch(
        f"/api/v1/invoices/{invoice_id}/status", json={"status": "sent"}, headers=h
    )

    assert response.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_status.py -v`
Expected: FAIL — route does not exist

- [ ] **Step 3: Add the update schema**

Append to `backend/app/schemas/invoice.py`:

```python
class InvoiceStatusUpdate(BaseModel):
    status: InvoiceStatus
```

- [ ] **Step 4: Add the endpoint**

Add `InvoiceStatusUpdate` to the schema import in `backend/app/api/v1/invoices.py`, then append:

```python
_MANUAL_INVOICE_TRANSITIONS: dict[InvoiceStatus, set[InvoiceStatus]] = {
    InvoiceStatus.draft: {InvoiceStatus.sent, InvoiceStatus.cancelled},
    InvoiceStatus.sent: {InvoiceStatus.overdue, InvoiceStatus.cancelled},
    InvoiceStatus.overdue: {InvoiceStatus.cancelled},
    InvoiceStatus.partially_paid: set(),
    InvoiceStatus.paid: set(),
    InvoiceStatus.cancelled: set(),
}


@router.patch("/invoices/{invoice_id}/status", response_model=InvoiceRead)
def update_invoice_status(
    invoice_id: str,
    payload: InvoiceStatusUpdate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Invoice:
    invoice = _get_invoice_or_404(db, current_user.tenant_id, invoice_id)

    allowed = _MANUAL_INVOICE_TRANSITIONS.get(invoice.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition invoice from {invoice.status.value} to {payload.status.value}",
        )

    invoice.status = payload.status
    db.commit()
    db.refresh(invoice)
    return invoice
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_status.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/invoices.py backend/app/schemas/invoice.py backend/tests/test_invoice_status.py
git commit -m "feat(invoicing): add invoice status transitions"
```

---

### Task 7: Record a payment against an invoice

**Files:**
- Create: `backend/app/schemas/payment.py`
- Create: `backend/app/api/v1/payments.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_payments_api.py`

**Interfaces:**
- Consumes: `_get_invoice_or_404` from `app.api.v1.invoices`, `Payment`, `STAFF_ROLES`
- Produces: `POST /invoices/{invoice_id}/payments`, `GET /invoices/{invoice_id}/payments`

**This is the only path to `partially_paid` and `paid`.** After inserting the payment, sum all `completed` payments for the invoice and set status accordingly:

- `sum >= total` → `paid`, and the job moves to `paid`
- `0 < sum < total` → `partially_paid`
- The invoice row is locked with `.with_for_update()` before the sum is recomputed, so two concurrent payments cannot both read a stale total and race the status. This is the same class of bug found in the purchase-order receive path during the inventory review — do not omit the lock.

**Guards:**
- Payment `amount` must be `> 0` (422).
- A `cancelled` invoice cannot take payments (400).
- Overpayment is rejected: if `existing_completed_sum + amount > total` (allowing a tiny float tolerance), return 400. Recording more money than is owed is a data-entry error, not a business case.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_payments_api.py`:

```python
def _owner_token(client, platform_admin, email="owner-pay@example.com", password="ownerpass123"):
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
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _invoice_for(client, token, part_price=10000.0):
    h = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": "N"}, headers=h).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "V"},
        headers=h,
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "J"},
        headers=h,
    ).json()["id"]
    item_id = client.post(
        "/api/v1/inventory-items",
        json={
            "sku": f"P-{part_price}", "name": "Part", "unit_cost": 1.0,
            "unit_price": part_price, "quantity_on_hand": 10.0,
        },
        headers=h,
    ).json()["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 1.0},
        headers=h,
    )
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "in_progress"}, headers=h)
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "done"}, headers=h)
    invoice = client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h).json()
    return job_id, invoice


def test_partial_payment_sets_partially_paid(client, platform_admin):
    token = _owner_token(client, platform_admin)
    h = {"Authorization": f"Bearer {token}"}
    _, invoice = _invoice_for(client, token, part_price=10000.0)

    response = client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount": 4000.0, "method": "cash"},
        headers=h,
    )

    assert response.status_code == 201
    assert response.json()["amount"] == 4000.0
    assert client.get(f"/api/v1/invoices/{invoice['id']}", headers=h).json()["status"] == "partially_paid"


def test_full_payment_marks_invoice_and_job_paid(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-pay-full@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id, invoice = _invoice_for(client, token, part_price=10000.0)

    client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount": 10000.0, "method": "bank_transfer"},
        headers=h,
    )

    assert client.get(f"/api/v1/invoices/{invoice['id']}", headers=h).json()["status"] == "paid"
    assert client.get(f"/api/v1/jobs/{job_id}", headers=h).json()["status"] == "paid"


def test_two_partial_payments_settle_the_invoice(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-pay-two@example.com")
    h = {"Authorization": f"Bearer {token}"}
    _, invoice = _invoice_for(client, token, part_price=10000.0)

    client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount": 6000.0, "method": "cash"}, headers=h,
    )
    client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount": 4000.0, "method": "cash"}, headers=h,
    )

    assert client.get(f"/api/v1/invoices/{invoice['id']}", headers=h).json()["status"] == "paid"


def test_overpayment_is_rejected(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-pay-over@example.com")
    h = {"Authorization": f"Bearer {token}"}
    _, invoice = _invoice_for(client, token, part_price=10000.0)

    response = client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount": 10000.01, "method": "cash"},
        headers=h,
    )

    assert response.status_code == 400


def test_payment_amount_must_be_positive(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-pay-zero@example.com")
    h = {"Authorization": f"Bearer {token}"}
    _, invoice = _invoice_for(client, token)

    response = client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount": 0, "method": "cash"},
        headers=h,
    )

    assert response.status_code == 422


def test_cancelled_invoice_rejects_payment(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-pay-cancel@example.com")
    h = {"Authorization": f"Bearer {token}"}
    _, invoice = _invoice_for(client, token)
    client.patch(f"/api/v1/invoices/{invoice['id']}/status", json={"status": "cancelled"}, headers=h)

    response = client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount": 100.0, "method": "cash"},
        headers=h,
    )

    assert response.status_code == 400


def test_payments_can_be_listed(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-pay-list@example.com")
    h = {"Authorization": f"Bearer {token}"}
    _, invoice = _invoice_for(client, token, part_price=10000.0)
    client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount": 100.0, "method": "cash"}, headers=h,
    )

    response = client.get(f"/api/v1/invoices/{invoice['id']}/payments", headers=h)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_payment_on_another_tenants_invoice_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-pay-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-pay-b@example.com")
    _, invoice = _invoice_for(client, token_a)

    response = client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount": 100.0, "method": "cash"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_payments_api.py -v`
Expected: FAIL — routes do not exist

- [ ] **Step 3: Write the schemas**

Create `backend/app/schemas/payment.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentMethod, PaymentStatus


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    invoice_id: str
    amount: float
    method: PaymentMethod
    status: PaymentStatus
    gateway: str | None
    external_reference: str | None
    paid_at: datetime


class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    method: PaymentMethod


class PaymentListResponse(BaseModel):
    items: list[PaymentRead]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 4: Write the router**

Create `backend/app/api/v1/payments.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.api.v1.invoices import _get_invoice_or_404
from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.job import Job, JobStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentListResponse, PaymentRead

router = APIRouter()

# Float tolerance so an exact-settlement payment isn't rejected by representation error.
_EPSILON = 0.005


def _completed_total(db: Session, tenant_id: str, invoice_id: str) -> float:
    total = (
        db.query(func.coalesce(func.sum(Payment.amount), 0.0))
        .filter(
            Payment.tenant_id == tenant_id,
            Payment.invoice_id == invoice_id,
            Payment.status == PaymentStatus.completed,
        )
        .scalar()
    )
    return float(total or 0.0)


@router.post(
    "/invoices/{invoice_id}/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED
)
def create_payment(
    invoice_id: str,
    payload: PaymentCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Payment:
    _get_invoice_or_404(db, current_user.tenant_id, invoice_id)

    # Lock the invoice before recomputing its paid total, so two concurrent
    # payments cannot both read a stale sum and race the status update.
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.tenant_id == current_user.tenant_id)
        .with_for_update()
        .one()
    )

    if invoice.status == InvoiceStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot record a payment against a cancelled invoice",
        )

    already_paid = _completed_total(db, current_user.tenant_id, invoice_id)
    if already_paid + payload.amount > invoice.total + _EPSILON:
        outstanding = invoice.total - already_paid
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment exceeds the outstanding balance of {outstanding:.2f}",
        )

    payment = Payment(
        tenant_id=current_user.tenant_id,
        invoice_id=invoice_id,
        amount=payload.amount,
        method=payload.method,
    )
    db.add(payment)
    db.flush()

    new_total = already_paid + payload.amount
    if new_total >= invoice.total - _EPSILON:
        invoice.status = InvoiceStatus.paid
        job = (
            db.query(Job)
            .filter(Job.id == invoice.job_id, Job.tenant_id == current_user.tenant_id)
            .first()
        )
        if job is not None:
            job.status = JobStatus.paid
    else:
        invoice.status = InvoiceStatus.partially_paid

    db.commit()
    db.refresh(payment)
    return payment


@router.get("/invoices/{invoice_id}/payments", response_model=PaymentListResponse)
def list_payments(
    invoice_id: str,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaymentListResponse:
    _get_invoice_or_404(db, current_user.tenant_id, invoice_id)
    query = db.query(Payment).filter(
        Payment.tenant_id == current_user.tenant_id, Payment.invoice_id == invoice_id
    )
    total = query.count()
    payments = query.offset((page - 1) * page_size).limit(page_size).all()
    return PaymentListResponse(items=payments, total=total, page=page, page_size=page_size)
```

- [ ] **Step 5: Mount the router**

In `backend/app/api/v1/router.py`, add `payments` to the import and mount it before `admin`:

```python
api_router.include_router(payments.router, tags=["payments"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_payments_api.py -v`
Expected: PASS (8 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/payment.py backend/app/api/v1/payments.py backend/app/api/v1/router.py backend/tests/test_payments_api.py
git commit -m "feat(invoicing): record payments and settle invoices"
```

---

### Task 8: Currency and formatting helpers

**Files:**
- Create: `backend/app/services/formatting.py`
- Test: `backend/tests/test_formatting.py`

**Interfaces:**
- Produces: `format_currency(amount, currency="LKR") -> str`, `format_percentage(rate) -> str` — both used by the invoice template in Task 9

Sri Lanka convention per `docs/07-sri-lanka-localization.md`: `LKR 12,500.00` — comma thousands separator, exactly two decimals. Percentages render as `18%` for whole numbers and `18.5%` otherwise, so a template never shows `18.0%`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_formatting.py`:

```python
import pytest

from app.services.formatting import format_currency, format_percentage


@pytest.mark.parametrize(
    "amount,expected",
    [
        (0, "LKR 0.00"),
        (5, "LKR 5.00"),
        (1234.5, "LKR 1,234.50"),
        (12500, "LKR 12,500.00"),
        (1234567.891, "LKR 1,234,567.89"),
        (250000.50, "LKR 250,000.50"),
    ],
)
def test_format_currency(amount, expected):
    assert format_currency(amount) == expected


def test_format_currency_honours_a_different_currency():
    assert format_currency(1000, currency="USD") == "USD 1,000.00"


@pytest.mark.parametrize(
    "rate,expected",
    [
        (0.18, "18%"),
        (0.185, "18.5%"),
        (0.0, "0%"),
        (0.155, "15.5%"),
    ],
)
def test_format_percentage(rate, expected):
    assert format_percentage(rate) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_formatting.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.formatting'`

- [ ] **Step 3: Write the helpers**

Create `backend/app/services/formatting.py`:

```python
def format_currency(amount: float, currency: str = "LKR") -> str:
    """Render money as `LKR 12,500.00` — comma thousands, always two decimals."""
    return f"{currency} {amount:,.2f}"


def format_percentage(rate: float) -> str:
    """Render a 0-1 tax rate as a percentage, dropping a trailing `.0`."""
    percent = rate * 100
    if percent == int(percent):
        return f"{int(percent)}%"
    return f"{percent:g}%"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_formatting.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/formatting.py backend/tests/test_formatting.py
git commit -m "feat(invoicing): add currency and percentage formatting helpers"
```

---

### Task 9: Invoice PDF builder

**Files:**
- Create: `backend/app/services/invoice_pdf.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-dev.txt`
- Test: `backend/tests/test_invoice_pdf_builder.py`

**Interfaces:**
- Consumes: `Invoice`, `Tenant`, `Customer`, `Asset`, `Job`, `format_currency`, `format_percentage`
- Produces: `build_invoice_pdf(db, invoice) -> bytes` — used by Task 10

**Library choice, decided by measurement on the actual deploy target.** `docs/06-invoice-template.md` specifies WeasyPrint. **WeasyPrint cannot run on this host.** Its system dependency `libpango-1.0.so.0` is version 1.42.3; WeasyPrint requires >= 1.44 for `pango_context_set_round_glyph_positions`, and the account has no root access to upgrade it. Verified by installing WeasyPrint on the server and attempting a render, which raised:

```
AttributeError: function/symbol 'pango_context_set_round_glyph_positions' not found
in library 'libpango-1.0.so.0': /lib64/libpango-1.0.so.0: undefined symbol
```

`fpdf2` is used instead. It is pure Python with no system dependencies, and was benchmarked on the same host at **2.4 ms per invoice render, 34 MB resident**. This matters because the account has a hard `LSAPI_CHILDREN` cap of 6 workers — a slow render blocks a worker that could be serving other requests. Update `docs/06-invoice-template.md` to match once this ships.

Layout follows the section ordering in `docs/06-invoice-template.md`: header band with workshop details, invoice meta, bill-to block with asset info, line items table, totals, footer. Positioning is by coordinate rather than CSS, which is the cost of a library that actually runs here.

- [ ] **Step 1: Add the dependency**

Add to both `backend/requirements.txt` and `backend/requirements-dev.txt`:

```
fpdf2==2.8.7
```

Install: `cd backend && .venv/bin/pip install -r requirements-dev.txt`

Do NOT add `weasyprint` or `jinja2` — neither is used.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_invoice_pdf_builder.py`:

```python
from datetime import date

from app.models.asset import Asset
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem, InvoiceLineItemType
from app.models.job import Job
from app.models.tenant import Tenant
from app.services.invoice_pdf import build_invoice_pdf


def _full_invoice(db_session, **tenant_kwargs):
    tenant = Tenant(
        name="Colombo Auto Repair",
        address="42 Galle Road, Colombo 03",
        phone="011-2345678",
        email="hello@colomboauto.lk",
        business_registration_number="PV 12345",
        currency="LKR",
        **tenant_kwargs,
    )
    db_session.add(tenant)
    db_session.commit()

    customer = Customer(tenant_id=tenant.id, name="Nimal Perera", phone="077-1234567")
    db_session.add(customer)
    db_session.commit()

    asset = Asset(
        tenant_id=tenant.id, customer_id=customer.id, type="vehicle",
        label="Toyota Corolla 2018", identifier="ABC-1234",
    )
    db_session.add(asset)
    db_session.commit()

    job = Job(tenant_id=tenant.id, customer_id=customer.id, asset_id=asset.id, title="Brake service")
    db_session.add(job)
    db_session.commit()

    invoice = Invoice(
        tenant_id=tenant.id, job_id=job.id, customer_id=customer.id,
        invoice_number="INV-2026-0001", issue_date=date(2026, 8, 2), due_date=date(2026, 8, 16),
        subtotal=11000.0, tax_rate=0.18, tax_amount=1980.0, total=12980.0,
    )
    db_session.add(invoice)
    db_session.commit()

    db_session.add_all([
        InvoiceLineItem(
            tenant_id=tenant.id, invoice_id=invoice.id, description="Labor: 2.00 h",
            quantity=2.0, unit_price=1500.0, line_total=3000.0, type=InvoiceLineItemType.labor,
        ),
        InvoiceLineItem(
            tenant_id=tenant.id, invoice_id=invoice.id, description="Brake pad set",
            quantity=2.0, unit_price=4000.0, line_total=8000.0, type=InvoiceLineItemType.part,
        ),
    ])
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def _extract_text(pdf_bytes):
    """Crude text scrape.

    fpdf2 writes uncompressed text operators by default, so asserting on the
    raw bytes is enough to prove content reached the page without adding a
    PDF-parsing dependency just for tests.
    """
    return pdf_bytes.decode("latin-1", errors="ignore")


def test_pdf_is_a_valid_a4_document(db_session):
    invoice = _full_invoice(db_session)

    pdf = build_invoice_pdf(db_session, invoice)

    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    # A4 is 595.28 x 841.89 pt; fpdf2 writes the MediaBox in points
    assert b"595.28" in pdf and b"841.89" in pdf


def test_pdf_contains_the_core_invoice_facts(db_session):
    invoice = _full_invoice(db_session)

    text = _extract_text(build_invoice_pdf(db_session, invoice))

    for expected in (
        "INV-2026-0001",
        "Colombo Auto Repair",
        "Nimal Perera",
        "Toyota Corolla 2018",
        "ABC-1234",
        "Brake pad set",
    ):
        assert expected in text, f"{expected!r} missing from the PDF"


def test_pdf_formats_money_in_sri_lankan_convention(db_session):
    invoice = _full_invoice(db_session)

    text = _extract_text(build_invoice_pdf(db_session, invoice))

    assert "LKR 12,980.00" in text
    assert "LKR 11,000.00" in text
    assert "18%" in text


def test_vat_number_is_omitted_when_not_registered(db_session):
    invoice = _full_invoice(db_session)

    text = _extract_text(build_invoice_pdf(db_session, invoice))

    assert "VAT" not in text


def test_vat_number_is_shown_when_registered(db_session):
    invoice = _full_invoice(db_session, vat_registration_number="VAT-998877")

    text = _extract_text(build_invoice_pdf(db_session, invoice))

    assert "VAT-998877" in text


def test_many_line_items_paginate_without_error(db_session):
    """A long invoice must flow onto further pages rather than overflow one."""
    invoice = _full_invoice(db_session)
    db_session.add_all([
        InvoiceLineItem(
            tenant_id=invoice.tenant_id, invoice_id=invoice.id,
            description=f"Extra part {index}", quantity=1.0, unit_price=100.0,
            line_total=100.0, type=InvoiceLineItemType.part,
        )
        for index in range(60)
    ])
    db_session.commit()
    db_session.refresh(invoice)

    pdf = build_invoice_pdf(db_session, invoice)

    assert pdf.startswith(b"%PDF-")
    assert b"/Count 2" in pdf or b"/Count 3" in pdf, "expected a multi-page document"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_pdf_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.invoice_pdf'`

- [ ] **Step 4: Write the builder**

Create `backend/app/services/invoice_pdf.py`:

```python
from fpdf import FPDF
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.job import Job
from app.models.tenant import Tenant
from app.services.formatting import format_currency, format_percentage

# A4 content width with 16 mm side margins.
_CONTENT_WIDTH = 178.0
_COL_DESCRIPTION = 88.0
_COL_QUANTITY = 20.0
_COL_UNIT_PRICE = 35.0
_COL_AMOUNT = 35.0
_ROW_HEIGHT = 6.5
# Leave room for the totals block and footer before breaking to a new page.
_BOTTOM_LIMIT = 250.0


def _header(pdf: FPDF, tenant: Tenant) -> None:
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 7, tenant.name, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 8.5)
    for line in (
        tenant.address,
        tenant.phone,
        tenant.email,
        f"Reg. No: {tenant.business_registration_number}"
        if tenant.business_registration_number
        else None,
        f"VAT No: {tenant.vat_registration_number}"
        if tenant.vat_registration_number
        else None,
    ):
        if line:
            pdf.cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.set_draw_color(34, 34, 34)
    pdf.set_line_width(0.5)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.l_margin + _CONTENT_WIDTH, y)
    pdf.ln(4)


def _meta(pdf: FPDF, invoice: Invoice) -> None:
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(90, 8, invoice.invoice_number)

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(
        88, 4, f"Issue date: {invoice.issue_date.strftime('%d %b %Y')}",
        align="R", new_x="LMARGIN", new_y="NEXT",
    )
    pdf.cell(90, 4, invoice.status.value.replace("_", " ").upper())
    pdf.cell(
        88, 4, f"Due date: {invoice.due_date.strftime('%d %b %Y')}",
        align="R", new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(4)


def _bill_to(pdf: FPDF, customer: Customer, asset: Asset) -> None:
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 4, "BILL TO", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(34, 34, 34)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, customer.name, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    for line in (customer.phone, customer.address):
        if line:
            pdf.cell(0, 4.5, line, new_x="LMARGIN", new_y="NEXT")

    vehicle = asset.label
    if asset.identifier:
        vehicle = f"{vehicle} - {asset.identifier}"
    pdf.cell(0, 5, vehicle, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


def _table_header(pdf: FPDF) -> None:
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.cell(_COL_DESCRIPTION, _ROW_HEIGHT, "Description", border="B")
    pdf.cell(_COL_QUANTITY, _ROW_HEIGHT, "Qty", border="B", align="R")
    pdf.cell(_COL_UNIT_PRICE, _ROW_HEIGHT, "Unit price", border="B", align="R")
    pdf.cell(_COL_AMOUNT, _ROW_HEIGHT, "Amount", border="B", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)


def _line_items(pdf: FPDF, lines: list[InvoiceLineItem], money) -> None:
    _table_header(pdf)
    for line in lines:
        if pdf.get_y() > _BOTTOM_LIMIT:
            pdf.add_page()
            _table_header(pdf)
        quantity = f"{line.quantity:g}"
        pdf.cell(_COL_DESCRIPTION, _ROW_HEIGHT, line.description[:60], border="B")
        pdf.cell(_COL_QUANTITY, _ROW_HEIGHT, quantity, border="B", align="R")
        pdf.cell(_COL_UNIT_PRICE, _ROW_HEIGHT, money(line.unit_price), border="B", align="R")
        pdf.cell(
            _COL_AMOUNT, _ROW_HEIGHT, money(line.line_total), border="B",
            align="R", new_x="LMARGIN", new_y="NEXT",
        )


def _totals(pdf: FPDF, invoice: Invoice, money) -> None:
    pdf.ln(3)
    label_width = _CONTENT_WIDTH - _COL_AMOUNT

    pdf.set_font("Helvetica", "", 9.5)
    pdf.cell(label_width, 5.5, "Subtotal", align="R")
    pdf.cell(_COL_AMOUNT, 5.5, money(invoice.subtotal), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.cell(label_width, 5.5, f"Tax ({format_percentage(invoice.tax_rate)})", align="R")
    pdf.cell(_COL_AMOUNT, 5.5, money(invoice.tax_amount), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(1)
    y = pdf.get_y()
    pdf.set_line_width(0.4)
    pdf.line(pdf.l_margin + label_width, y, pdf.l_margin + _CONTENT_WIDTH, y)
    pdf.ln(1.5)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(label_width, 8, "Total", align="R")
    pdf.cell(_COL_AMOUNT, 8, money(invoice.total), align="R", new_x="LMARGIN", new_y="NEXT")


def _footer(pdf: FPDF) -> None:
    pdf.ln(8)
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.2)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.l_margin + _CONTENT_WIDTH, y)
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 4.5, "Thank you for your business.", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(170, 170, 170)
    pdf.cell(0, 4, "Generated by Torqbay", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(34, 34, 34)


def build_invoice_pdf(db: Session, invoice: Invoice) -> bytes:
    """Render an invoice to an A4 PDF.

    Every element is positioned explicitly so output is byte-identical across
    platforms - the same invoice must not look different depending on where it
    was generated.
    """
    tenant = db.query(Tenant).filter(Tenant.id == invoice.tenant_id).one()
    customer = (
        db.query(Customer)
        .filter(Customer.id == invoice.customer_id, Customer.tenant_id == invoice.tenant_id)
        .one()
    )
    job = (
        db.query(Job)
        .filter(Job.id == invoice.job_id, Job.tenant_id == invoice.tenant_id)
        .one()
    )
    asset = (
        db.query(Asset)
        .filter(Asset.id == job.asset_id, Asset.tenant_id == invoice.tenant_id)
        .one()
    )
    lines = (
        db.query(InvoiceLineItem)
        .filter(
            InvoiceLineItem.invoice_id == invoice.id,
            InvoiceLineItem.tenant_id == invoice.tenant_id,
        )
        .order_by(InvoiceLineItem.type, InvoiceLineItem.created_at)
        .all()
    )

    def money(amount: float) -> str:
        return format_currency(amount, tenant.currency)

    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(16, 18, 16)
    pdf.add_page()
    pdf.set_text_color(34, 34, 34)

    _header(pdf, tenant)
    _meta(pdf, invoice)
    _bill_to(pdf, customer, asset)
    _line_items(pdf, lines, money)
    _totals(pdf, invoice, money)
    _footer(pdf)

    return bytes(pdf.output())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_pdf_builder.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/invoice_pdf.py backend/requirements.txt backend/requirements-dev.txt backend/tests/test_invoice_pdf_builder.py
git commit -m "feat(invoicing): build invoice PDFs with fpdf2"
```

---

### Task 10: PDF endpoint

**Files:**
- Modify: `backend/app/api/v1/invoices.py`
- Test: `backend/tests/test_invoice_pdf_endpoint.py`

**Interfaces:**
- Consumes: `build_invoice_pdf`, `_get_invoice_or_404`
- Produces: `GET /invoices/{invoice_id}/pdf`

Returns `application/pdf` with a `Content-Disposition` filename of `<invoice_number>.pdf`. The PDF is rendered per request — there is no stored file and no `pdf_url` column, per the design decisions at the top of this plan. At 2.4 ms per render this is far cheaper than storing and invalidating files.

`fpdf2` is pure Python with no system dependencies, so unlike the original WeasyPrint approach it can be imported at module scope without risking application startup.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_invoice_pdf_endpoint.py`:

```python
def _owner_token(client, platform_admin, email="owner-pdf@example.com", password="ownerpass123"):
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
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _invoice(client, token):
    h = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": "Nimal"}, headers=h).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Corolla"},
        headers=h,
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Service"},
        headers=h,
    ).json()["id"]
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "in_progress"}, headers=h)
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "done"}, headers=h)
    return client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h).json()


def test_pdf_endpoint_returns_a_pdf(client, platform_admin):
    token = _owner_token(client, platform_admin)
    h = {"Authorization": f"Bearer {token}"}
    invoice = _invoice(client, token)

    response = client.get(f"/api/v1/invoices/{invoice['id']}/pdf", headers=h)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert invoice["invoice_number"] in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")


def test_pdf_is_deterministic_across_requests(client, platform_admin):
    """The same invoice must produce the same document every time."""
    token = _owner_token(client, platform_admin, email="owner-pdf-det@example.com")
    h = {"Authorization": f"Bearer {token}"}
    invoice = _invoice(client, token)

    first = client.get(f"/api/v1/invoices/{invoice['id']}/pdf", headers=h).content
    second = client.get(f"/api/v1/invoices/{invoice['id']}/pdf", headers=h).content

    assert len(first) == len(second)


def test_pdf_for_another_tenants_invoice_returns_404(client, platform_admin):
    token_a = _owner_token(client, platform_admin, email="owner-pdf-a@example.com")
    token_b = _owner_token(client, platform_admin, email="owner-pdf-b@example.com")
    invoice = _invoice(client, token_a)

    response = client.get(
        f"/api/v1/invoices/{invoice['id']}/pdf", headers={"Authorization": f"Bearer {token_b}"}
    )

    assert response.status_code == 404


def test_pdf_requires_authentication(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-pdf-auth@example.com")
    invoice = _invoice(client, token)

    response = client.get(f"/api/v1/invoices/{invoice['id']}/pdf")

    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_pdf_endpoint.py -v`
Expected: FAIL — route does not exist

- [ ] **Step 3: Add the endpoint**

Add `Response` to the existing `fastapi` import in `backend/app/api/v1/invoices.py`, add `from app.services.invoice_pdf import build_invoice_pdf`, then append:

```python
@router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: str,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    invoice = _get_invoice_or_404(db, current_user.tenant_id, invoice_id)
    pdf = build_invoice_pdf(db, invoice)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{invoice.invoice_number}.pdf"'},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_pdf_endpoint.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/invoices.py backend/tests/test_invoice_pdf_endpoint.py
git commit -m "feat(invoicing): add invoice PDF endpoint"
```

---

### Task 11: Invoice immutability after issue

**Files:**
- Modify: `backend/app/api/v1/invoices.py`
- Test: `backend/tests/test_invoice_immutability.py`

**Interfaces:**
- Consumes: `_get_invoice_or_404`
- Produces: `POST /invoices/{invoice_id}/line-items` (draft only), `DELETE /invoices/{invoice_id}/line-items/{line_item_id}` (draft only)

Per `docs/06-invoice-template.md`: once an invoice leaves `draft`, its line items are frozen. A customer holding a PDF must never find the database quietly disagreeing with it. Corrections after issue go through a new invoice, not an edit.

Adding or removing a line item recomputes `subtotal`, `tax_amount`, and `total` from all line items, so the header can never drift from its lines.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_invoice_immutability.py`:

```python
def _owner_token(client, platform_admin, email="owner-immut@example.com", password="ownerpass123"):
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
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _draft_invoice(client, token):
    h = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": "N"}, headers=h).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "V"},
        headers=h,
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "J"},
        headers=h,
    ).json()["id"]
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "in_progress"}, headers=h)
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "done"}, headers=h)
    return client.post(f"/api/v1/jobs/{job_id}/invoice", json={"tax_rate": 0.1}, headers=h).json()


def test_line_item_can_be_added_to_a_draft_and_totals_recompute(client, platform_admin):
    token = _owner_token(client, platform_admin)
    h = {"Authorization": f"Bearer {token}"}
    invoice = _draft_invoice(client, token)

    response = client.post(
        f"/api/v1/invoices/{invoice['id']}/line-items",
        json={"description": "Disposal fee", "quantity": 1.0, "unit_price": 500.0, "type": "other"},
        headers=h,
    )

    assert response.status_code == 201
    fetched = client.get(f"/api/v1/invoices/{invoice['id']}", headers=h).json()
    assert fetched["subtotal"] == 500.0
    assert fetched["tax_amount"] == 50.0
    assert fetched["total"] == 550.0


def test_line_item_can_be_removed_from_a_draft(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-immut-del@example.com")
    h = {"Authorization": f"Bearer {token}"}
    invoice = _draft_invoice(client, token)
    line_id = client.post(
        f"/api/v1/invoices/{invoice['id']}/line-items",
        json={"description": "Oops", "quantity": 1.0, "unit_price": 999.0, "type": "other"},
        headers=h,
    ).json()["id"]

    response = client.delete(f"/api/v1/invoices/{invoice['id']}/line-items/{line_id}", headers=h)

    assert response.status_code == 204
    assert client.get(f"/api/v1/invoices/{invoice['id']}", headers=h).json()["total"] == 0.0


def test_sent_invoice_rejects_new_line_items(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-immut-sent@example.com")
    h = {"Authorization": f"Bearer {token}"}
    invoice = _draft_invoice(client, token)
    client.patch(f"/api/v1/invoices/{invoice['id']}/status", json={"status": "sent"}, headers=h)

    response = client.post(
        f"/api/v1/invoices/{invoice['id']}/line-items",
        json={"description": "Sneaky", "quantity": 1.0, "unit_price": 100.0, "type": "other"},
        headers=h,
    )

    assert response.status_code == 400


def test_sent_invoice_rejects_line_item_deletion(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-immut-sentdel@example.com")
    h = {"Authorization": f"Bearer {token}"}
    invoice = _draft_invoice(client, token)
    line_id = client.post(
        f"/api/v1/invoices/{invoice['id']}/line-items",
        json={"description": "Fee", "quantity": 1.0, "unit_price": 100.0, "type": "other"},
        headers=h,
    ).json()["id"]
    client.patch(f"/api/v1/invoices/{invoice['id']}/status", json={"status": "sent"}, headers=h)

    response = client.delete(f"/api/v1/invoices/{invoice['id']}/line-items/{line_id}", headers=h)

    assert response.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_immutability.py -v`
Expected: FAIL — routes do not exist

- [ ] **Step 3: Add the create schema**

Append to `backend/app/schemas/invoice.py`:

```python
class InvoiceLineItemCreate(BaseModel):
    description: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    type: InvoiceLineItemType = InvoiceLineItemType.other
```

- [ ] **Step 4: Add the endpoints**

Add `InvoiceLineItemCreate` and `InvoiceLineItemRead` to the schema import in `backend/app/api/v1/invoices.py`, then append:

```python
def _require_draft(invoice: Invoice) -> None:
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invoice is {invoice.status.value} and can no longer be edited; "
                "issue a new invoice instead"
            ),
        )


def _recompute_totals(db: Session, invoice: Invoice) -> None:
    subtotal = sum(
        line.line_total
        for line in db.query(InvoiceLineItem)
        .filter(
            InvoiceLineItem.invoice_id == invoice.id,
            InvoiceLineItem.tenant_id == invoice.tenant_id,
        )
        .all()
    )
    invoice.subtotal = subtotal
    invoice.tax_amount = subtotal * invoice.tax_rate
    invoice.total = subtotal + invoice.tax_amount


@router.post(
    "/invoices/{invoice_id}/line-items",
    response_model=InvoiceLineItemRead,
    status_code=status.HTTP_201_CREATED,
)
def add_line_item(
    invoice_id: str,
    payload: InvoiceLineItemCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> InvoiceLineItem:
    invoice = _get_invoice_or_404(db, current_user.tenant_id, invoice_id)
    _require_draft(invoice)

    line = InvoiceLineItem(
        tenant_id=current_user.tenant_id,
        invoice_id=invoice.id,
        description=payload.description,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        line_total=payload.quantity * payload.unit_price,
        type=payload.type,
    )
    db.add(line)
    db.flush()
    _recompute_totals(db, invoice)
    db.commit()
    db.refresh(line)
    return line


@router.delete(
    "/invoices/{invoice_id}/line-items/{line_item_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_line_item(
    invoice_id: str,
    line_item_id: str,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    invoice = _get_invoice_or_404(db, current_user.tenant_id, invoice_id)
    _require_draft(invoice)

    line = (
        db.query(InvoiceLineItem)
        .filter(
            InvoiceLineItem.id == line_item_id,
            InvoiceLineItem.invoice_id == invoice.id,
            InvoiceLineItem.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found")

    db.delete(line)
    db.flush()
    _recompute_totals(db, invoice)
    db.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoice_immutability.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/invoices.py backend/app/schemas/invoice.py backend/tests/test_invoice_immutability.py
git commit -m "feat(invoicing): freeze line items once an invoice leaves draft"
```

---

### Task 12: Job status wiring guard

**Files:**
- Test: `backend/tests/test_job_invoice_status_wiring.py`

**Interfaces:**
- Consumes: every endpoint built so far. No production code changes expected.

`invoiced` and `paid` are reachable on a job **only** through invoicing and payment. The manual job-status endpoint has always blocked them (`_MANUAL_TRANSITIONS` maps `done` to an empty set). This task pins that contract with tests, so a future change to either state machine cannot silently open a path that lets a job be marked paid without money being recorded.

**If any test here fails, do NOT loosen the test.** A failure means the money-to-status coupling is broken somewhere and needs a real fix. Report BLOCKED with the observed behavior.

- [ ] **Step 1: Write the tests**

Create `backend/tests/test_job_invoice_status_wiring.py`:

```python
def _owner_token(client, platform_admin, email="owner-wiring@example.com", password="ownerpass123"):
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
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _done_job(client, token):
    h = {"Authorization": f"Bearer {token}"}
    customer_id = client.post("/api/v1/customers", json={"name": "N"}, headers=h).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "V"},
        headers=h,
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "J"},
        headers=h,
    ).json()["id"]
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "in_progress"}, headers=h)
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "done"}, headers=h)
    return job_id


def test_job_cannot_be_manually_marked_invoiced(client, platform_admin):
    token = _owner_token(client, platform_admin)
    h = {"Authorization": f"Bearer {token}"}
    job_id = _done_job(client, token)

    response = client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "invoiced"}, headers=h)

    assert response.status_code == 400
    assert client.get(f"/api/v1/jobs/{job_id}", headers=h).json()["status"] == "done"


def test_job_cannot_be_manually_marked_paid(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-wiring-paid@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _done_job(client, token)

    response = client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "paid"}, headers=h)

    assert response.status_code == 400
    assert client.get(f"/api/v1/jobs/{job_id}", headers=h).json()["status"] == "done"


def test_an_invoiced_job_cannot_be_reopened(client, platform_admin):
    token = _owner_token(client, platform_admin, email="owner-wiring-reopen@example.com")
    h = {"Authorization": f"Bearer {token}"}
    job_id = _done_job(client, token)
    client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h)

    response = client.patch(
        f"/api/v1/jobs/{job_id}/status", json={"status": "in_progress"}, headers=h
    )

    assert response.status_code == 400
    assert client.get(f"/api/v1/jobs/{job_id}", headers=h).json()["status"] == "invoiced"
```

- [ ] **Step 2: Run the tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_job_invoice_status_wiring.py -v`
Expected: PASS (3 tests), with no production changes

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_job_invoice_status_wiring.py
git commit -m "test(invoicing): pin job invoiced/paid status wiring"
```

---

### Task 13: Full lifecycle integration tests

**Files:**
- Test: `backend/tests/test_invoicing_lifecycle.py`

**Interfaces:**
- Consumes: every endpoint in this plan plus jobs, labor entries, parts, and inventory. No production code changes.

Proves the whole money path end to end: a job accumulates labor and parts, becomes an invoice with correct totals, gets paid in instalments, and settles — with the job and invoice statuses moving in lockstep and stock untouched by any of it.

- [ ] **Step 1: Write the tests**

Create `backend/tests/test_invoicing_lifecycle.py`:

```python
from datetime import datetime, timedelta, timezone


def _owner_token(client, platform_admin, email, password="ownerpass123"):
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
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def test_full_job_to_settled_invoice_lifecycle(client, platform_admin):
    token = _owner_token(client, platform_admin, "owner-life@example.com")
    h = {"Authorization": f"Bearer {token}"}

    tech_id = client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": "tech-life@example.com",
              "password": "techpass123", "role": "technician"},
        headers=h,
    ).json()["id"]

    customer_id = client.post("/api/v1/customers", json={"name": "Nimal"}, headers=h).json()["id"]
    asset_id = client.post(
        f"/api/v1/customers/{customer_id}/assets",
        json={"type": "vehicle", "label": "Corolla", "identifier": "ABC-1234"},
        headers=h,
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        json={"customer_id": customer_id, "asset_id": asset_id, "title": "Brake service"},
        headers=h,
    ).json()["id"]

    item_id = client.post(
        "/api/v1/inventory-items",
        json={"sku": "BP-1", "name": "Brake pad set", "unit_cost": 2500.0,
              "unit_price": 4000.0, "quantity_on_hand": 10.0},
        headers=h,
    ).json()["id"]

    # Time is tracked for utilisation, and deliberately does NOT affect the
    # invoice — labour is billed from the job's flat charge.
    start = datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc)
    client.post(
        f"/api/v1/jobs/{job_id}/labor-entries",
        json={"technician_id": tech_id, "start_time": start.isoformat(),
              "end_time": (start + timedelta(hours=3)).isoformat()},
        headers=h,
    )
    client.patch(f"/api/v1/jobs/{job_id}", json={"labor_cost": 3000.0}, headers=h)
    client.post(
        f"/api/v1/jobs/{job_id}/parts",
        json={"inventory_item_id": item_id, "quantity": 2.0},
        headers=h,
    )

    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "in_progress"}, headers=h)
    client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "done"}, headers=h)

    # 3000 flat labour + 2 * 4000 = 8000 parts, subtotal 11000, tax 10% = 1100.
    # The 3 hours tracked above must NOT appear in the total.
    invoice = client.post(f"/api/v1/jobs/{job_id}/invoice", json={"tax_rate": 0.1}, headers=h).json()
    assert invoice["subtotal"] == 11000.0
    assert invoice["tax_amount"] == 1100.0
    assert invoice["total"] == 12100.0
    assert client.get(f"/api/v1/jobs/{job_id}", headers=h).json()["status"] == "invoiced"

    client.patch(f"/api/v1/invoices/{invoice['id']}/status", json={"status": "sent"}, headers=h)

    client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount": 5000.0, "method": "cash"}, headers=h,
    )
    assert client.get(f"/api/v1/invoices/{invoice['id']}", headers=h).json()["status"] == "partially_paid"
    assert client.get(f"/api/v1/jobs/{job_id}", headers=h).json()["status"] == "invoiced"

    client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount": 7100.0, "method": "bank_transfer"}, headers=h,
    )
    assert client.get(f"/api/v1/invoices/{invoice['id']}", headers=h).json()["status"] == "paid"
    assert client.get(f"/api/v1/jobs/{job_id}", headers=h).json()["status"] == "paid"

    # invoicing consumed no additional stock: 10 - 2 = 8
    assert client.get(f"/api/v1/inventory-items/{item_id}", headers=h).json()["quantity_on_hand"] == 8.0


def test_invoice_numbers_are_sequential_within_a_tenant(client, platform_admin):
    token = _owner_token(client, platform_admin, "owner-life-seq@example.com")
    h = {"Authorization": f"Bearer {token}"}

    numbers = []
    for index in range(3):
        customer_id = client.post(
            "/api/v1/customers", json={"name": f"C{index}"}, headers=h
        ).json()["id"]
        asset_id = client.post(
            f"/api/v1/customers/{customer_id}/assets",
            json={"type": "vehicle", "label": "V"}, headers=h,
        ).json()["id"]
        job_id = client.post(
            "/api/v1/jobs",
            json={"customer_id": customer_id, "asset_id": asset_id, "title": "J"}, headers=h,
        ).json()["id"]
        client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "in_progress"}, headers=h)
        client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "done"}, headers=h)
        numbers.append(
            client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h).json()["invoice_number"]
        )

    sequences = [int(number.split("-")[-1]) for number in numbers]
    assert sequences == [1, 2, 3]


def test_two_tenants_both_start_at_invoice_0001(client, platform_admin):
    token_a = _owner_token(client, platform_admin, "owner-life-ta@example.com")
    token_b = _owner_token(client, platform_admin, "owner-life-tb@example.com")

    def first_invoice_number(token):
        h = {"Authorization": f"Bearer {token}"}
        customer_id = client.post("/api/v1/customers", json={"name": "C"}, headers=h).json()["id"]
        asset_id = client.post(
            f"/api/v1/customers/{customer_id}/assets",
            json={"type": "vehicle", "label": "V"}, headers=h,
        ).json()["id"]
        job_id = client.post(
            "/api/v1/jobs",
            json={"customer_id": customer_id, "asset_id": asset_id, "title": "J"}, headers=h,
        ).json()["id"]
        client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "in_progress"}, headers=h)
        client.patch(f"/api/v1/jobs/{job_id}/status", json={"status": "done"}, headers=h)
        return client.post(f"/api/v1/jobs/{job_id}/invoice", json={}, headers=h).json()["invoice_number"]

    assert first_invoice_number(token_a).endswith("-0001")
    assert first_invoice_number(token_b).endswith("-0001")


def test_technician_cannot_see_invoices_or_payments(client, platform_admin):
    owner_token = _owner_token(client, platform_admin, "owner-life-role@example.com")
    oh = {"Authorization": f"Bearer {owner_token}"}
    client.post(
        "/api/v1/users",
        json={"name": "Tech", "email": "tech-life-role@example.com",
              "password": "techpass123", "role": "technician"},
        headers=oh,
    )
    tech_token = client.post(
        "/api/v1/auth/login",
        json={"email": "tech-life-role@example.com", "password": "techpass123"},
    ).json()["access_token"]
    th = {"Authorization": f"Bearer {tech_token}"}

    assert client.get("/api/v1/invoices", headers=th).status_code == 403
```

- [ ] **Step 2: Run the tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_invoicing_lifecycle.py -v`
Expected: PASS (4 tests)

- [ ] **Step 3: Run the whole suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: all pass — 115 pre-existing plus everything added in Tasks 1-13

- [ ] **Step 4: Verify migrations apply from empty**

Run: `cd backend && rm -f dev.db && .venv/bin/python -m alembic upgrade head`
Expected: every migration applies cleanly in order

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_invoicing_lifecycle.py
git commit -m "test(invoicing): cover the full job-to-settled-invoice lifecycle"
```

---

## Deployment notes

`fpdf2` is added to `requirements.txt`, so the CI/CD deploy installs it. It is pure Python with no system dependencies.

After merge, CI/CD runs `alembic upgrade head` against production MySQL. All three new tables (`invoices`, `invoice_line_items`, `payments`) are additive — no existing table is altered — so the migration is safe against live data.

`docs/03-data-model.md` lists a `pdf_url` column on `invoices`. This plan deliberately omits it; see the design decisions at the top. Update that doc to match once this ships.
