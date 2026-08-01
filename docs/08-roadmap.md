# Roadmap

Each phase below becomes its own implementation plan (via the
`writing-plans` process) when its turn comes — this doc just sequences
them and states what's in/out per phase. Order reflects two things:
what's foundational vs. additive, and what has no external-service risk
(cheap, build early) vs. what depends on a third-party integration
(payment gateways, WhatsApp/Meta approval — build once the foundation is
proven).

## Phase 1 — MVP (core product)

A single workshop owner can run their whole business day-to-day.

- Multi-tenant auth (JWT), 4 roles, tenant provisioning (admin-created)
- Customers, assets, jobs (simple lifecycle), labor entries, parts usage
- Full inventory: items, suppliers, purchase orders, stock in/out
- Invoicing: generation from a completed job, A4 PDF (logo + tenant info),
  tenant-sequential numbering
- Payments: manual recording only (cash/card/bank_transfer)
- Finance: expenses, recurring expenses (rent/utilities), payroll
  (salary/hourly, Sri Lanka EPF/ETF, payroll runs → auto-expense)
- Reports: technician performance, workshop KPIs, job profitability
  (all computed via aggregation queries, no separate reporting tables)
- Mobile app: all screens in the [mobile app doc](05-mobile-app.md) except
  advisor, payroll runs beyond viewing own payslip, and subscription settings

**Explicitly not in Phase 1**: business advisor, repair guides, payment
gateway, SMS/WhatsApp, AI features, self-serve signup/billing.

## Phase 2 — Business Advisor

- Rule-based [insights engine](09-business-advisor.md): labor pricing,
  hiring signals, true cost of a hire, cash flow, overdue invoices, dead
  stock, technician profitability, delegation, retention
- Pure computation over Phase 1 data — no external dependency, cheapest
  high-value addition to build right after the core is stable

## Phase 3 — Repair Guides

- Shared, platform-level [repair guide library](11-repair-guides.md):
  search by asset/make/model/component, external video links, technician
  contribution + platform moderation
- Independent of every other phase — content + search only

## Phase 4 — Payments & Notifications

- Payment gateway integration: PayHere first, LankaQR follow-up
  (see [localization doc](07-sri-lanka-localization.md))
- Webhook handling for async payment confirmation
- SMS notifications (local aggregator) for job-ready and payment reminders
- WhatsApp notifications (Cloud API or BSP) — requires Meta template
  approval lead time, start that process before writing integration code
- Notification log/history screen in the app

## Phase 5 — SaaS Subscription Billing

- `subscription_plans` + `tenant_subscriptions` tables (already designed
  in [data model doc](03-data-model.md), just unused until now)
- Platform admin UI/endpoints to define plans and assign tenants
- Recurring billing (likely via the same payment gateway chosen in
  Phase 4, or a dedicated billing-capable processor if PayHere doesn't
  support recurring charges well — evaluate at Phase 5 start)
- Plan limit enforcement (max users, max jobs/month) at the API layer
- Natural point to gate AI features (Phase 6) behind a paid tier, since
  those carry a real per-request cost

## Phase 6 — AI Features

See [AI features doc](10-ai-features.md) for full design and internal
build order (chat → reports → customer chatbot → MCP server). Depends on
Phase 2's advisor computation layer (reused as the tool-calling layer)
and, for the customer chatbot specifically, Phase 4's WhatsApp
integration.

## Phase 7+ — Not yet planned in detail

Candidates only, not committed: offline-capable mobile app for field use,
customer self-service portal, barcode/QR scanning for inventory, advanced
analytics/exports, multi-country expansion. Revisit once earlier phases
are live and real usage tells us what's actually needed.

## Why this order

Phase 1 alone is a complete, sellable product — a workshop can fully
replace a spreadsheet/paper system with it. Phases 2-3 are cheap,
dependency-free additions that raise the product's value fast. Phase 4
introduces real external-integration risk (gateway approval, Meta
template review) so it comes once the core is proven, not before. Phase
5 monetizes the platform itself. Phase 6 is the most speculative and
highest-cost-per-use layer, deliberately last and gated behind a paid
tier once Phase 5 exists to enforce that gate.
