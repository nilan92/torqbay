# Mobile App (Expo)

Built with Expo + Expo Router (file-based navigation), NativeWind for
styling, React Query for server state. See `expo-native-ui` and
`expo-tailwind-setup` skills in this environment when implementation
starts.

## Design principle: straightforward over powerful

The user of this app is a workshop owner or staff member, not a software
person — most screens should be understandable without a manual. This
governs every screen decision below, not just a nice-to-have:

- Prefer a short list of clear actions over a settings-heavy screen with
  every option exposed. Advanced/rare options move to a secondary screen,
  not a toggle cluttering the main one.
- Numbers are labeled in plain words, not accounting jargon — "Money owed
  to you" not "Accounts receivable"; "Your cut after costs" not "Net
  margin." This applies directly to the [business advisor](09-business-advisor.md)
  screen, where the whole point is plain-language advice, not a finance
  report.
- Every destructive or hard-to-reverse action (cancel a job, delete an
  inventory item with history, void an invoice) gets a plain-language
  confirmation, not a generic "Are you sure?"
- New staff (especially technicians) should be productive after one
  walkthrough: the job detail screen is the one they'll open dozens of
  times a day, so it gets the most design attention, not the settings
  screens an owner opens once a month.

## Navigation structure

```
app/
  (auth)/
    login.tsx
    forgot-password.tsx
  (tabs)/                      -- role-aware bottom tabs, see below
    dashboard.tsx
    jobs/
      index.tsx                -- job list, filterable by status
      [id].tsx                 -- job detail: parts, labor, status actions
      new.tsx
    customers/
      index.tsx
      [id].tsx                 -- customer detail + their assets + job history
      new.tsx
    inventory/
      index.tsx                -- stock list, low-stock flagged
      [id].tsx
      purchase-orders.tsx
    finance/
      invoices.tsx
      expenses.tsx              -- includes recurring expenses (rent, utilities)
      invoice/[id].tsx         -- invoice detail, PDF preview/share, record payment
      payroll/
        index.tsx               -- payroll runs, owner/manager only
        run/[id].tsx            -- payslip breakdown per staff member
        my-payslips.tsx         -- technician's own pay history only
    performance/
      index.tsx                -- workshop KPIs
      technicians.tsx          -- per-technician performance
      advisor.tsx              -- business advisor: plain-language insight cards
    settings/
      index.tsx
      profile.tsx
      tenant.tsx                -- owner only: business info, logo, tax rate
      staff.tsx                 -- owner/manager only: manage users, pay terms
      subscription.tsx          -- owner only, Phase 5
  _layout.tsx
```

## Tab visibility by role

Not every role sees every tab — the bottom tab bar is filtered client-side
based on the logged-in user's role (defense in depth; the backend also
enforces this on every request regardless of what the UI shows):

| Tab | Owner | Manager | Technician | Front desk |
|---|---|---|---|---|
| Dashboard | ✓ | ✓ | ✓ (own jobs summary) | ✓ |
| Jobs | ✓ | ✓ | ✓ (assigned only) | ✓ |
| Customers | ✓ | ✓ | — | ✓ |
| Inventory | ✓ | ✓ | view only | ✓ |
| Finance | ✓ | ✓ | — | ✓ (no expenses/payroll) |
| Payroll | ✓ | ✓ (not own pay terms) | own payslips only | — |
| Performance | ✓ | ✓ | — | — |
| Business advisor | ✓ | ✓ | — | — |
| Settings | ✓ (full) | limited | limited | limited |

## Key screens — practical notes

- **Job detail**: primary screen technicians live in. Big obvious status
  buttons (`Start` / `Mark Done`), a simple "add part used" flow that
  searches inventory by name/SKU, and a start/stop timer for labor entries
  rather than manual time entry — reduces friction on a shop floor.
- **Invoice detail**: shows PDF preview inline (via `react-native-pdf` or
  a WebView), a "Share" button (native share sheet — WhatsApp/SMS/email
  all come free through this without custom integration), and payment
  recording as a simple method-select + amount form.
- **Dashboard**: role-appropriate summary cards — owner/manager see
  revenue + open jobs + low stock alerts; technician sees their assigned
  jobs only.
- **Advisor screen**: a short stack of dismissible cards (not a report to
  scroll through) — one insight, one plain-language sentence of why it
  matters, one suggested action, a "dismiss"/"remind me later" control.
  See [business advisor doc](09-business-advisor.md) for the rule catalog.

## Offline behavior

Not building full offline-first sync for Phase 1 — a workshop has wifi/
data at the counter. React Query's built-in caching gives a reasonable
"last known data visible, retries on reconnect" experience for free.
Revisit only if field use (e.g. mobile mechanics with no signal) becomes
a real requirement.

## API client

Generate a typed client from the backend's OpenAPI schema
(`openapi-typescript` + a thin fetch wrapper that attaches the JWT and
handles 401 → refresh-token retry in one place). No hand-maintained
per-endpoint request functions — regenerate the client whenever the
backend schema changes.
