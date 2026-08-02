# Data Model

All tenant-owned tables include `id` (PK), `tenant_id` (FK, indexed),
`created_at`, `updated_at`, `deleted_at` (soft delete) unless noted
otherwise. Types are conceptual, not final SQL types.

## Platform-level (not tenant-scoped)

### `tenants`
The workshop business itself.

| Field | Notes |
|---|---|
| id | PK |
| name | business name |
| business_registration_number | SL: BRN, shown on invoices |
| vat_registration_number | nullable — only if VAT-registered |
| address, phone, email | |
| logo_url | for invoice branding |
| currency | default `LKR` |
| default_tax_rate | percentage, tenant-configurable (see [localization doc](07-sri-lanka-localization.md)) |
| is_active | platform admin can suspend a tenant |
| created_at | |

### `subscription_plans` (Phase 5)
Plans the platform admin defines (e.g. Basic/Pro).

| Field | Notes |
|---|---|
| id | PK |
| name, price_monthly, currency | |
| max_users, max_jobs_per_month | plan limits |
| features | JSON — feature flags per plan |

### `tenant_subscriptions` (Phase 5)

| Field | Notes |
|---|---|
| tenant_id | FK |
| plan_id | FK |
| status | `trial` / `active` / `past_due` / `suspended` / `cancelled` |
| current_period_start/end | |
| next_billing_date | |

## Tenant-scoped: identity

### `users`
Staff accounts within a tenant.

| Field | Notes |
|---|---|
| tenant_id | FK |
| name, email, phone | |
| password_hash | |
| role | `owner` / `manager` / `technician` / `frontdesk` |
| is_active | |

### `customers`
The workshop's clients (not app users — they don't log in).

| Field | Notes |
|---|---|
| tenant_id | FK |
| name, phone, email, address | phone is primary contact (SMS/WhatsApp) |
| notes | |

### `assets`
The item being repaired, owned by a customer (vehicle, device, appliance —
kept generic so it fits any repair vertical).

| Field | Notes |
|---|---|
| tenant_id | FK |
| customer_id | FK |
| type | e.g. `vehicle`, `electronics`, `appliance` |
| label | e.g. make/model or device name |
| identifier | e.g. plate number, serial number |
| notes | |

## Tenant-scoped: jobs

### `jobs`
The core unit of work.

| Field | Notes |
|---|---|
| tenant_id | FK |
| customer_id, asset_id | FK |
| assigned_technician_id | FK to `users`, nullable until assigned |
| title, description | |
| status | `open` / `in_progress` / `done` / `invoiced` / `paid` / `cancelled` |
| created_at, started_at, completed_at | timestamps drive turnaround-time KPIs |
| labor_cost | computed from `job_labor_entries` or set manually |

### `job_labor_entries`
Time logged by technicians — feeds technician performance metrics.

| Field | Notes |
|---|---|
| job_id | FK |
| technician_id | FK to `users` |
| start_time, end_time | |
| hourly_rate | rate at time of entry (snapshot, not live lookup) |

### `job_parts`
Parts consumed by a job — feeds job profitability.

| Field | Notes |
|---|---|
| job_id | FK |
| inventory_item_id | FK |
| quantity | |
| unit_cost_at_time, unit_price_at_time | snapshot at time of use, so later inventory price changes don't retroactively change past job profitability |

## Tenant-scoped: inventory

### `suppliers`

| Field | Notes |
|---|---|
| tenant_id | FK |
| name, contact_info | |

### `inventory_items`

| Field | Notes |
|---|---|
| tenant_id | FK |
| sku, name, category | |
| unit_cost, unit_price | |
| quantity_on_hand | |
| reorder_threshold | triggers low-stock alert |
| supplier_id | FK, nullable |

### `purchase_orders` / `purchase_order_items`
Restocking from suppliers.

| Field | Notes |
|---|---|
| purchase_orders.tenant_id, supplier_id, status | `draft`/`ordered`/`received` |
| purchase_order_items.po_id, inventory_item_id, quantity, unit_cost | |

Receiving a PO increments the linked `inventory_items.quantity_on_hand`;
using parts on a job decrements it. Both are the only two write paths to
stock quantity — no other code path should mutate it directly.

## Tenant-scoped: finance

### `invoices`

| Field | Notes |
|---|---|
| tenant_id | FK |
| job_id, customer_id | FK |
| invoice_number | tenant-scoped sequential (e.g. `INV-2026-0001`), not globally sequential |
| issue_date, due_date | |
| subtotal, tax_rate, tax_amount, total | |
| status | `draft` / `sent` / `partially_paid` / `paid` / `overdue` / `cancelled` |
| *(no pdf_url)* | PDFs are generated on demand, not stored — see [invoice template doc](06-invoice-template.md) |

### `invoice_line_items`

| Field | Notes |
|---|---|
| invoice_id | FK |
| description, quantity, unit_price, line_total | |
| type | `labor` / `part` / `other` |

### `payments`
Deliberately provider-agnostic so Phase 4 gateway/QR support is additive.

| Field | Notes |
|---|---|
| tenant_id | FK |
| invoice_id | FK |
| amount | |
| method | `cash` / `card` / `bank_transfer` / `gateway` / `qr` |
| status | `pending` / `completed` / `failed` / `refunded` |
| gateway | nullable — e.g. `payhere`, `lankaqr` (Phase 4) |
| external_reference | nullable — gateway transaction ID |
| paid_at | |

### `expenses`
General workshop overhead, not tied to a specific job (rent, utilities,
salaries) — needed so "finances" covers the whole business, not just job
revenue.

| Field | Notes |
|---|---|
| tenant_id | FK |
| category | e.g. `rent`, `utilities`, `salaries`, `supplies` |
| amount, date, notes | |

## Tenant-scoped: payroll

### `employee_compensation`
Current and historical pay terms per staff member — kept as a history
(not just a column on `users`) so a past raise doesn't rewrite what a
payslip from six months ago should have paid.

| Field | Notes |
|---|---|
| tenant_id | FK |
| user_id | FK to `users` |
| pay_type | `fixed_salary` / `hourly` |
| base_amount | monthly amount if fixed, hourly rate if hourly |
| epf_employer_rate | default 12% — Sri Lanka Employees' Provident Fund, employer share |
| epf_employee_rate | default 8% — deducted from employee's pay |
| etf_employer_rate | default 3% — Employees' Trust Fund, employer-only, no employee deduction |
| effective_from, effective_to | nullable `effective_to` = currently active |

### `payroll_runs`

| Field | Notes |
|---|---|
| tenant_id | FK |
| period_start, period_end | |
| status | `draft` / `finalized` / `paid` |

### `payslips`

| Field | Notes |
|---|---|
| payroll_run_id | FK |
| user_id | FK |
| gross_pay | `base_amount` if fixed; if hourly, `hours_worked × hourly_rate` where hours come from that period's `job_labor_entries` |
| epf_employee_deduction, epf_employer_contribution, etf_employer_contribution | computed from the rates on `employee_compensation` at the time |
| adjustments | single signed amount + note (e.g. advance repayment, bonus) — not a full ledger; add one only if disputes over deduction history become a real problem |
| net_pay | `gross_pay − epf_employee_deduction + adjustments` |
| paid_at | |

**Why this matters for hiring decisions**: `gross_pay` is what shows up on
a payslip, but `gross_pay + epf_employer_contribution + etf_employer_contribution`
is the shop's *actual* cost of that employee — a ~15% gap that's easy to
forget when budgeting a new hire. The [business advisor doc](09-business-advisor.md)
surfaces this "fully loaded cost" explicitly rather than letting the
owner reason from gross salary alone.

**Finance integration**: finalizing a payroll run auto-creates one
`expenses` row (category `salaries`, amount = sum of all
`gross_pay + employer contributions` in the run) so payroll cost flows
into the existing KPI/cash-flow aggregation without a parallel finance
system. Payslip detail stays in the payroll tables for
per-employee/compliance records.

**Not in Phase 1**: payslip PDF export. Payslip data is viewable in-app;
add a printable PDF (reusing the same fpdf2 approach as invoices)
only if staff actually need a physical/digital payslip handed to them.

## Tenant-scoped: recurring expenses

### `recurring_expenses`
Solves the "re-enter the electricity bill every month" annoyance for
rent, utilities, insurance, subscriptions, etc.

| Field | Notes |
|---|---|
| tenant_id | FK |
| category | e.g. `rent`, `utilities`, `internet`, `insurance` |
| amount | |
| frequency | `weekly` / `monthly` / `yearly` |
| next_due_date | |
| is_active | pause without deleting history |

A daily scheduled check creates an `expenses` row whenever
`next_due_date` is reached and advances it by the frequency — the only
"background job" Phase 1 needs, simple enough to not require a real task
queue (see [architecture doc](02-architecture.md)).

## Tenant-scoped: notifications (Phase 4)

### `notifications`
Log of outbound customer messages — one row per send attempt, regardless
of channel.

| Field | Notes |
|---|---|
| tenant_id | FK |
| customer_id | FK |
| channel | `sms` / `whatsapp` |
| trigger | `job_status_change` / `invoice_sent` / `payment_reminder` |
| message | rendered text |
| status | `sent` / `failed` / `delivered` (if provider reports delivery) |
| sent_at | |

No separate "template" table for Phase 1 — message templates live as
simple string-format functions in code (`services/notifications.py`).
Move templates into the database only if non-technical staff need to
edit wording themselves without a deploy — not a known requirement yet.

## Performance metrics: computed, not stored

Technician performance, workshop KPIs, and job profitability are all
**derived from the tables above via aggregation queries**, not stored in
their own tables:

- *Technician performance* = aggregate `job_labor_entries` + `jobs` by
  `technician_id` (jobs completed, avg time, on-time rate)
- *Workshop KPIs* = aggregate `invoices` + `expenses` by month/week
  (revenue, profit trend); aggregate `jobs` for turnaround time and repeat
  customers
- *Job profitability* = per job: `invoice total` − (`job_parts` cost sum +
  `job_labor_entries` cost sum)

Reason: storing pre-computed snapshots adds a cache-invalidation problem
(numbers going stale when a job is edited after the fact) for a query
load that plain SQL aggregation handles fine at workshop scale. Revisit
only if dashboard query latency becomes a real problem.

## Tenant-scoped: business advisor

### `insight_dismissals`
The only storage the advisor needs — everything else it reads is already
computed from existing tables (see [business advisor doc](09-business-advisor.md)
for the rule catalog). This table just remembers what a tenant already
acknowledged, so a dismissed tip doesn't reappear every time they open
the dashboard.

| Field | Notes |
|---|---|
| tenant_id | FK |
| insight_key | e.g. `labor_pricing_thin`, `hiring_signal` — identifies which rule |
| dismissed_at | |
| dismissed_until | nullable — e.g. "remind me again in 30 days" instead of forever |

## Entity relationship summary

```
tenants ─┬─ users ─── employee_compensation
         ├─ customers ─── assets
         ├─ jobs ─┬─ job_labor_entries
         │        └─ job_parts ─── inventory_items
         ├─ inventory_items ─── suppliers
         ├─ purchase_orders ─── purchase_order_items ─── inventory_items
         ├─ invoices ─┬─ invoice_line_items
         │            └─ payments
         ├─ expenses ─── recurring_expenses (generates expenses)
         ├─ payroll_runs ─── payslips (finalizing generates an expense)
         ├─ notifications
         ├─ insight_dismissals
         └─ tenant_subscriptions ─── subscription_plans (platform-level)
```
