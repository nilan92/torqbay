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
