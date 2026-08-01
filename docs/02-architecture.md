# Architecture

## Stack

| Layer | Choice | Why |
|---|---|---|
| Mobile app | React Native via **Expo** (Expo Router) | Cross-platform, OTA updates, fast iteration; user requirement |
| Backend | **Python + FastAPI** | Async-native, auto-generated OpenAPI spec the mobile app can codegen a typed client from, lighter than Django for an API-only service |
| ORM | SQLAlchemy 2.0 + Alembic (migrations) | Standard, explicit, works well with FastAPI |
| Database | **MySQL 8** | User requirement |
| Auth | JWT (access + refresh tokens) | Stateless, works well with mobile clients |
| PDF generation | **WeasyPrint** (HTML/CSS → PDF) | Lets us design the invoice as an HTML/CSS template (easy to make "nice") rather than hand-coding PDF drawing calls |
| File storage | Local disk (dev) → S3-compatible object storage (prod) | Logos, generated invoice PDFs |
| Background jobs | FastAPI `BackgroundTasks` initially; upgrade to a queue (e.g. Celery/RQ) only if volume demands it | YAGNI — a real task queue is unnecessary until notification/PDF volume is high |

## Multi-tenancy: shared database, row-level isolation

One MySQL database serves all tenants. Every tenant-owned table has a
`tenant_id` column (foreign key to `tenants.id`).

- **Enforcement point**: a FastAPI dependency reads `tenant_id` out of the
  authenticated user's JWT and injects it into a request-scoped "current
  tenant" context. All repository/query functions require this context and
  automatically filter `WHERE tenant_id = :tenant_id` — there is no code
  path that queries tenant data without it.
- **Why not schema-per-tenant or DB-per-tenant**: migrations would need to
  run once per tenant, multiplying operational complexity for no real
  benefit at the expected scale (small-to-medium workshop businesses,
  not enterprises needing hard data-residency separation).
- **Platform admin** (SaaS operator) is a separate `is_superadmin` user
  type, not tied to any tenant, who can list/create/suspend tenants.

## Module map (backend)

```
app/
  core/          config, JWT security, tenant-context dependency, password hashing
  db/             session management, base model (id, tenant_id, timestamps, soft-delete mixin)
  models/         SQLAlchemy models — one file per entity group (see data model doc)
  schemas/        Pydantic request/response schemas
  api/v1/         routers: auth, tenants, users, customers, jobs, inventory,
                  invoices, payments, notifications, performance, subscriptions
  services/       business logic: invoice numbering + PDF rendering,
                  performance aggregation queries, notification dispatch
  integrations/   external providers: payment gateway, SMS, WhatsApp,
                  Claude API (AI features, Phase 6) — each behind a small
                  interface so providers can be swapped
  templates/      Jinja2 HTML templates (invoice PDF)
```

**Integration abstraction**: payments, SMS, and WhatsApp are each defined
as a small interface (`send(to, message) -> result`, `charge(...) -> result`)
with a "log only" / no-op implementation for Phase 1 and a real provider
implementation swapped in for Phase 4. This is the same pluggable pattern
already used for the `Payment.method` field — the point is that adding a
real provider later is a new implementation of an existing interface, not
a redesign.

## Mobile app architecture

- **Expo Router** (file-based navigation) — see [Mobile App doc](05-mobile-app.md)
  for the full screen/route map.
- **API client**: generated from the backend's OpenAPI schema
  (`openapi-typescript`) for typed requests — no hand-written fetch
  wrappers to keep in sync.
- **Auth token storage**: `expo-secure-store`.
- **State/data fetching**: React Query (TanStack Query) for server state —
  handles caching, refetch, and offline-ish retry without hand-rolled
  state management.
- **Styling**: NativeWind (Tailwind for React Native) — see
  `expo-tailwind-setup` skill already available in this environment.

## Request flow example (create a job)

1. Front-desk user opens "New Job" screen on mobile
2. App calls `POST /api/v1/jobs` with JWT in `Authorization` header
3. Backend: JWT verified → tenant context set → role check (front desk
   allowed) → job row inserted with `tenant_id` from context
4. Response returned, mobile app's React Query cache updated
5. On job completion, an invoice is generated server-side and a PDF stored;
   the mobile app fetches a signed URL to view/share it

## Environments

- **Dev**: local MySQL + local FastAPI + Expo Go / dev client
- **Staging/Prod**: managed MySQL (e.g. PlanetScale, RDS, or a Sri Lanka/
  Singapore-region host for latency), FastAPI behind a reverse proxy,
  object storage for PDFs/logos, Expo EAS Build for app store releases
