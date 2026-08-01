# Overview

## What this is

A multi-tenant SaaS application for repair/service workshops (auto repair,
electronics repair, appliance service, and similar) to run their business:
track jobs, inventory, invoicing, payments, staff performance, and overall
finances. Each workshop business is a **tenant** — its own isolated data,
staff, customers, and settings — inside one shared deployment.

Built as a React Native (Expo) mobile app talking to a Python (FastAPI)
backend, backed by MySQL. First market is Sri Lanka.

## Who uses it

Within one tenant (one workshop business), four roles:

| Role | Can do |
|---|---|
| **Owner/Admin** | Everything — finances, staff, settings, all jobs, subscription/billing |
| **Manager** | Day-to-day ops, sees finances/performance, cannot touch billing or delete tenant data |
| **Technician/Staff** | Sees only assigned jobs, logs time and parts used, updates job status — no financial visibility |
| **Front desk/Receptionist** | Creates customers and jobs, generates invoices, records payments — limited finance view, no performance/reports |

There is also a **platform admin** (you, the SaaS operator) who provisions
tenants and manages subscription plans — not a role within a tenant.

## Core workflow

1. Customer brings in an item (vehicle, device, appliance) → front desk creates a **Job**
2. Job assigned to a **Technician**, who logs time and parts used
3. Job moves through: `Open → In Progress → Done → Invoiced → Paid`
   (no formal quote/approval step — fits walk-in repair shops)
4. On completion, an **Invoice** (PDF, A4, workshop-branded) is generated from labor + parts
5. Payment recorded (cash/card/bank transfer today; gateway/QR in Phase 2)
6. Customer notified by SMS/WhatsApp at key steps (Phase 2)
7. Owner/Manager view dashboards: revenue, job profitability, technician performance

## What's explicitly in scope

- Multi-tenant SaaS (many workshop businesses, isolated data)
- Job/repair tracking with a simple lifecycle
- Full inventory management (stock levels, suppliers, purchase orders)
- Finance tracking (job profitability + general workshop expenses)
- Invoicing with A4 PDF output, workshop logo/branding
- Performance tracking: technician performance, workshop KPIs, job profitability
- Payment recording now; payment gateway + QR payments soon (Phase 2)
- SMS + WhatsApp customer notifications (Phase 2)
- SaaS subscription billing for tenants themselves (Phase 3)
- Sri Lanka as the first and only market for now (currency, tax, providers)

## What's explicitly out of scope (for now)

- Self-serve tenant signup with live payment (Phase 3 covers subscription
  billing, but initial tenant provisioning is admin-driven)
- Multi-currency / multi-country support
- Native inventory barcode scanning hardware integrations
- Customer-facing self-service portal (customers only receive
  notifications; they don't log in)
