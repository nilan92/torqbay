# Sri Lanka Localization

First and only market for now. Nothing below is hardcoded into logic —
it's tenant-configurable data, so expanding to another country later is a
config/data change, not a rewrite.

## Currency & tax

- **Currency**: LKR. Format `LKR 12,500.00` (comma thousands, 2 decimals).
  Store amounts as integer cents/minor units in the DB to avoid float
  rounding errors; format for display only.
- **VAT**: Sri Lanka's standard VAT rate has changed more than once in
  recent years (18% as of the most recent change I'm aware of) —
  **don't hardcode a rate in code**. `tenants.default_tax_rate` is set
  per tenant at onboarding and editable in settings, so a rate change or
  a tenant with a different rate (or VAT-exempt) is just a data edit.
  Confirm the current rate with the Sri Lanka Inland Revenue Department
  (IRD) at implementation time rather than trusting this doc.
- **Invoice fields**: Business Registration Number (BRN) and VAT
  Registration Number both have dedicated fields on `tenants` (VAT number
  nullable — not every small workshop is VAT-registered) and appear on
  the invoice PDF when set. See [invoice template doc](06-invoice-template.md).

## Phone numbers

- Store in E.164 format (`+94771234567`) regardless of how the user types
  it — normalize on input (strip leading `0`, add `+94`) so SMS/WhatsApp
  providers always receive a consistent format.

## Payment gateway (Phase 4)

Two realistic options, both fit the `payments.gateway` field already in
the data model without a schema change:

- **PayHere** — the dominant Sri Lankan payment aggregator for SMEs;
  supports local cards, mobile wallets. Easiest integration path for a
  local-first business, well-documented REST + hosted checkout.
- **LankaQR** — Central Bank of Sri Lanka's national interoperable QR
  standard; banks (and non-bank issuers) already support scanning it.
  Relevant if the goal is "any bank app can pay by scanning the
  workshop's QR," which fits the "QR payments" ask directly.

Recommendation when Phase 4 starts: PayHere first (single integration,
covers card + wallet), LankaQR as a follow-up for QR-specific in-person
payments. Both are additive — no rework of `payments`/`invoices` needed,
just a new `integrations/payhere.py` (or `lankaqr.py`) implementing the
existing payment-gateway interface.

## SMS provider (Phase 4)

Local aggregators (e.g. **notify.lk**, or direct APIs from **Dialog** or
**Mobitel**) generally deliver more reliably and cheaply to Sri Lankan
numbers than a global provider like Twilio. Recommendation: start with a
local aggregator with a simple REST API; the `integrations/sms.py`
interface (`send(to, message)`) means swapping providers later is a
one-file change.

## WhatsApp (Phase 4)

Use the **WhatsApp Business Cloud API** (Meta) directly, or through a
Business Solution Provider (e.g. Gupshup, 360dialog, Twilio) if you'd
rather not manage Meta's app review/verification process yourself.
Sri Lankan numbers work fine on the Cloud API. Message templates for
proactive notifications (job status, invoice sent, payment reminder) must
be pre-approved by Meta before use — plan for template approval lead time
before the Phase 4 build, not during it.

## Notification triggers (both channels)

Defined once in `services/notifications.py`, sent through whichever
channel(s) the tenant enables:

- Job status changes to `done` — "Your [asset] is ready for pickup"
- Invoice sent — link/PDF share
- Payment reminder — for `overdue` invoices, on a schedule (e.g. daily
  check, not real-time)


## Statutory payroll (Phase 1 payroll sub-plan)

Verified August 2026. Rates change with each national budget — re-confirm with
the Inland Revenue Department and the Department of Labour before implementing,
and keep every rate configurable rather than compiled in.

### EPF / ETF — the deductions that actually apply

| Fund | Employer | Employee | Basis |
|---|---|---|---|
| EPF (Employees' Provident Fund) | 12% | 8% | Total monthly earnings |
| ETF (Employees' Trust Fund) | 3% | — | Total monthly earnings |

Both are calculated on **total monthly earnings**, which is itself the evidence
that the workforce is salaried rather than hourly — see the labour billing note
in [data model](03-data-model.md).

### APIT / PAYE — usually zero for workshop staff

Personal relief is **LKR 1,800,000 per year (LKR 150,000 per month)** from
1 April 2025. Above that, progressive bands apply: 6%, 18%, 24%, 30%, 36%
(the old 12% band was removed).

**A typical mechanic earns well under the relief threshold, so their PAYE is
zero.** The payroll module's common case is EPF and ETF only. It still has to
handle APIT correctly for an owner or manager on a higher salary — but a
payslip showing no income tax is normal, not a bug.

### Gratuity — out of scope for most tenants

The Payment of Gratuity Act No. 12 of 1983 applies only to employers with
**more than 15 employees** in the preceding twelve months, and only to staff
who have completed **five years of service**. It is then half a month's
terminal salary per year of service.

Most target workshops are under 15 staff, so gratuity is **not implemented in
Phase 1**. Revisit if larger service centres become customers — it is a real
statutory liability, not an optional benefit.

### Sources

- [EPF, ETF and gratuity overview — Simplebooks](https://simplebooks.com/srilanka/epf-etf/)
- [Employees' Provident Fund — Central Bank of Sri Lanka](https://www.cbsl.gov.lk/en/employees-provident-fund)
- [APIT/PAYE tables 2025/26 — TaxCalculator.lk](https://taxcalculator.lk/apit-paye-tax-tables-2025-2026-complete-guide-for-sri-lankan-employers-and-hr-managers/)
- [Sri Lanka payroll tax and compliance guide 2026 — RemotePeople](https://remotepeople.com/countries/sri-lanka/hire-employees/payroll-tax/)
- [VAT changes 2026 — Conventus Law](https://conventuslaw.com/report/sri-lanka-vat-changes-2026-key-updates-businesses-must-know/)
- [VAT threshold reversal — EconomyNext](https://economynext.com/explainer-sri-lanka-govt-shelves-vat-threshold-reduction-on-political-economic-u-turn-276354/)
