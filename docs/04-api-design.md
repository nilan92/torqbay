# API Design

Base path: `/api/v1`. JSON in, JSON out. Auth via `Authorization: Bearer <JWT>`.

## Conventions

- Resource-based REST: `GET/POST /jobs`, `GET/PATCH/DELETE /jobs/{id}`
- Every authenticated request is implicitly scoped to the caller's tenant
  — no `tenant_id` is ever passed in the request body/query by the client;
  it's read from the JWT server-side. (Prevents a client from ever
  querying another tenant's data by passing a different ID.)
- Pagination: `?page=1&page_size=20` on all list endpoints, response
  wraps `{ items: [...], total, page, page_size }`
- Errors: standard shape `{ "detail": "message" }` with proper HTTP status
  codes (401 unauthenticated, 403 wrong role, 404 not found, 422 validation)
- Role checks are declared per-route (FastAPI dependency), not scattered
  in handler bodies

## Endpoint map

### Auth
- `POST /auth/login` — email + password → access + refresh token
- `POST /auth/refresh`
- `POST /auth/logout`

### Platform admin (superadmin only, separate auth)
- `POST /admin/tenants` — provision a new tenant + owner user
- `GET /admin/tenants`
- `PATCH /admin/tenants/{id}` — activate/suspend
- `GET /admin/subscription-plans`, `POST /admin/subscription-plans` (Phase 5)

### Users (owner/manager only, except self)
- `GET /users`
- `POST /users` — invite/create staff
- `PATCH /users/{id}` — role change, deactivate
- `GET /users/me`, `PATCH /users/me`

### Customers & assets
- `GET/POST /customers`
- `GET/PATCH /customers/{id}`
- `GET/POST /customers/{id}/assets`

### Jobs
- `GET/POST /jobs`
- `GET/PATCH /jobs/{id}`
- `PATCH /jobs/{id}/status` — enforces valid transitions (`open → in_progress → done → invoiced → paid`)
- `POST /jobs/{id}/labor-entries`
- `POST /jobs/{id}/parts` — also decrements inventory

### Inventory
- `GET/POST /inventory-items`
- `PATCH /inventory-items/{id}`
- `GET /inventory-items?low_stock=true`
- `GET/POST /suppliers`
- `GET/POST /purchase-orders`
- `PATCH /purchase-orders/{id}/receive` — increments stock

### Invoices & payments
- `POST /jobs/{id}/invoice` — generate invoice + PDF from a `done` job
- `GET /invoices`, `GET /invoices/{id}`
- `GET /invoices/{id}/pdf` — signed download URL
- `POST /invoices/{id}/payments` — record a payment (method = cash/card/bank_transfer today)
- `POST /invoices/{id}/payments/gateway` — Phase 4: initiate gateway/QR payment
- `POST /webhooks/payments/{gateway}` — Phase 4: gateway callback, unauthenticated but signature-verified

### Expenses
- `GET/POST /expenses`
- `PATCH/DELETE /expenses/{id}`
- `GET/POST /recurring-expenses`
- `PATCH /recurring-expenses/{id}` — edit amount or pause (`is_active`)

### Payroll (owner/manager only)
- `GET/POST /employee-compensation` — set/update a staff member's pay terms
- `GET/POST /payroll-runs`
- `POST /payroll-runs/{id}/finalize` — computes payslips, creates the linked expense
- `GET /payroll-runs/{id}/payslips`
- `GET /payslips/me` — technician's own payslip history, no one else's

### Notifications (Phase 4)
- `GET /notifications` — log/history per customer or tenant
- (Sending is triggered internally by job/invoice/payment events, not a
  client-called endpoint — see [architecture doc](02-architecture.md))

### Performance/reports
- `GET /reports/technician-performance?from=&to=`
- `GET /reports/workshop-kpis?from=&to=`
- `GET /reports/job-profitability?from=&to=`

### Business advisor (Phase 2 — see [business advisor doc](09-business-advisor.md))
- `GET /insights` — active, non-dismissed insights for the tenant
- `POST /insights/{key}/dismiss` — optional `snooze_days`

## Auth & role matrix (summary)

| Endpoint group | Owner | Manager | Technician | Front desk |
|---|---|---|---|---|
| Users | full | view only | — | — |
| Customers/Jobs | full | full | own jobs only | full |
| Inventory | full | full | view only | full |
| Invoices/Payments | full | full | — | full |
| Expenses/Recurring expenses | full | full | — | — |
| Payroll | full | full (not own pay terms) | own payslips only | — |
| Reports | full | full | — | — |
| Business advisor | full | full | — | — |
| Tenant settings/billing | full | — | — | — |

Full role/permission detail lives in code (`core/permissions.py`), not
duplicated here beyond this summary table.
