# Roadmap

Each phase below becomes its own implementation plan (via the
`writing-plans` process) when its turn comes — this doc just sequences
them and states what's in/out per phase.

## Phase 1 — MVP (core product)

A single workshop owner can run their whole business day-to-day.

- Multi-tenant auth (JWT), 4 roles, tenant provisioning (admin-created)
- Customers, assets, jobs (simple lifecycle), labor entries, parts usage
- Full inventory: items, suppliers, purchase orders, stock in/out
- Invoicing: generation from a completed job, A4 PDF (logo + tenant info),
  tenant-sequential numbering
- Payments: manual recording only (cash/card/bank_transfer)
- Expenses: general workshop overhead tracking
- Reports: technician performance, workshop KPIs, job profitability
  (all computed via aggregation queries, no separate reporting tables)
- Mobile app: all screens in the [mobile app doc](05-mobile-app.md) except
  subscription settings

**Explicitly not in Phase 1**: payment gateway, SMS/WhatsApp, self-serve
signup/billing.

## Phase 2 — Payments & notifications

- Payment gateway integration: PayHere first, LankaQR follow-up
  (see [localization doc](07-sri-lanka-localization.md))
- Webhook handling for async payment confirmation
- SMS notifications (local aggregator) for job-ready and payment reminders
- WhatsApp notifications (Cloud API or BSP) — requires Meta template
  approval lead time, start that process before writing integration code
- Notification log/history screen in the app

## Phase 3 — SaaS subscription billing

- `subscription_plans` + `tenant_subscriptions` tables (already designed
  in [data model doc](03-data-model.md), just unused until now)
- Platform admin UI/endpoints to define plans and assign tenants
- Recurring billing (likely via the same payment gateway chosen in
  Phase 2, or a dedicated billing-capable processor if PayHere doesn't
  support recurring charges well — evaluate at Phase 3 start)
- Plan limit enforcement (max users, max jobs/month) at the API layer

## Phase 4+ — Not yet planned in detail

Candidates only, not committed: offline-capable mobile app for field use,
customer self-service portal, barcode/QR scanning for inventory, advanced
analytics/exports, multi-country expansion. Revisit once Phases 1-3 are
live and real usage tells us what's actually needed.

## Why this order

Phase 1 alone is a complete, sellable product — a workshop can fully
replace a spreadsheet/paper system with it. Phases 2-3 are additive
layers the architecture already anticipates (pluggable payment methods,
provider-agnostic notification interfaces, subscription tables sitting
unused) specifically so building them later doesn't require reworking
Phase 1 code.
