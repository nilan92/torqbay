# Business Advisor

A rule-based insights engine that reads data the app already collects
(jobs, invoices, expenses, payroll, inventory) and surfaces plain-language
advice aimed at the specific arc a repair workshop goes through: one
person doing everything → first hire → small team → established
business. This is not a chatbot or an ML model — it's a fixed catalog of
checks, each one computed by a normal SQL aggregation, matching the
"computed, not stored" approach already used for performance metrics
(see [data model doc](03-data-model.md)).

## Why rules, not AI

Every insight below needs to be explainable and trustworthy to a
non-technical owner making real money decisions — "why is it telling me
this?" always has a one-line, auditable answer (a threshold on a number
they can also see themselves), not a black-box output. A rule engine also
costs nothing to run and never hallucinates a number. Revisit only if the
rule catalog genuinely can't express something valuable — not because
"AI" sounds more impressive.

## How it runs

`services/advisor.py` defines each rule as a small function:
`(tenant_id, db) -> Insight | None`. `GET /insights` runs all rules for
the tenant, filters out ones in `insight_dismissals` (and not yet past
`dismissed_until`), and returns what's left. Cheap enough to compute
on-demand — no caching needed until proven otherwise.

```
Insight = {
  key: str            # stable id, e.g. "labor_pricing_thin"
  severity: "info" | "warning" | "critical"
  title: str           # plain language, e.g. "Your labor pricing may be too thin"
  detail: str          # the number behind it, in the owner's terms
  action: str          # one concrete next step
}
```

## Growth stages

The advisor doesn't ask the owner what stage they're at — it infers it
from `users` (active technician count) and shapes which rules are most
relevant:

| Stage | Technician count | Focus |
|---|---|---|
| Solo | 1 (the owner) | Pricing, personal/business finance separation, knowing when to hire |
| First hire | 2 | True cost of an employee, defining pay structure, avoiding premature hiring |
| Small team | 3-6 | Per-technician profitability, delegating admin, cash flow with fixed payroll |
| Established | 7+ | Retention/repeat customers, reinvestment, avoiding customer concentration |

All rules run regardless of stage — the stage just affects which ones are
*likely* to fire and how the copy is framed, not which are technically
active.

## Rule catalog

Each rule names the pitfall it addresses, the data it reads, and the
threshold that fires it (thresholds are starting points — make them
tenant-configurable if real usage shows they need tuning per business).

### 1. Labor pricing may be too thin
**Pitfall**: undercharging for labor, common for solo operators who don't
account for their own time properly.
**Reads**: avg hourly rate charged (`invoice_line_items` where
`type = labor`) vs. avg fully-loaded technician cost (`employee_compensation`
+ employer EPF/ETF, or a reasonable owner-time estimate if solo).
**Fires**: charged rate leaves less than ~30% margin over cost.

### 2. Consider hiring — sustained backlog
**Pitfall**: staying overworked too long instead of hiring, or waiting
until burnout instead of using the data already in hand.
**Reads**: count of `open`/`in_progress` jobs per active technician,
averaged weekly.
**Fires**: backlog per technician stays above a capacity threshold for
4+ consecutive weeks (a single busy week doesn't fire this — sustained
trend only).

### 3. New hire's workload is low
**Pitfall**: the inverse mistake — hiring ahead of real demand, then not
noticing the new person is underutilized.
**Reads**: revenue or logged hours per technician in the weeks following
a new `employee_compensation` record.
**Fires**: new technician's utilization stays well below the team average
for 3+ weeks post-hire.

### 4. The true cost of your team
**Pitfall**: budgeting hires off gross salary alone and being surprised
by the real cost.
**Reads**: sum of `gross_pay + epf_employer_contribution + etf_employer_contribution`
across active `employee_compensation` records.
**Always shown** (informational, not a warning) once there's at least one
non-owner employee — this is a fact card, not a threshold-triggered alert.

### 5. Cash flow risk
**Pitfall**: expenses (including payroll) creeping up faster than
revenue, unnoticed until it's a crisis.
**Reads**: trailing 3-month revenue (`invoices`) vs. trailing 3-month
total (`expenses` + payroll-generated expense rows).
**Fires**: expense growth rate exceeds revenue growth rate over the
window.

### 6. Follow up on overdue invoices
**Pitfall**: money owed piling up because no one's actively chasing it.
**Reads**: sum of `invoices` where `status = overdue`.
**Fires**: overdue total exceeds ~20% of trailing-month revenue.

### 7. Capital tied up in unused stock
**Pitfall**: overstocking parts that never move, quietly eating cash.
**Reads**: `inventory_items` with no `job_parts` usage in N months,
weighted by `unit_cost × quantity_on_hand`.
**Fires**: tied-up value exceeds a meaningful threshold (e.g. a week's
average revenue).

### 8. Uneven technician profitability
**Pitfall**: not noticing one technician (or one job type) is
consistently less profitable, whether from pricing, skill gaps, or slow
jobs.
**Reads**: per-technician job profitability (see data model doc) once
2+ technicians exist.
**Fires**: largest gap between technicians exceeds a meaningful
percentage of average job profit.

### 9. Consider delegating admin work
**Pitfall**: the classic small-business bottleneck — the owner still
personally creating every invoice/job even after hiring front-desk staff.
**Reads**: share of jobs/invoices created by the `owner` role vs. total,
once a `frontdesk` role exists on the team.
**Fires**: owner is still creating a large majority of records despite
having staff who could.

### 10. Repeat customers are slipping
**Pitfall**: losing customers to competitors without noticing until
revenue drops — retention is cheaper to fix than new-customer acquisition.
**Reads**: share of customers with 2+ jobs in a trailing window, compared
to the prior window.
**Fires**: repeat rate drops meaningfully period over period.

### 11. Keep business and personal money separate
**Pitfall**: the most common solo-operator mistake — no clean separation
between business and personal finances, which makes tax time and
profitability both impossible to reason about.
**Reads**: nothing (not data-driven) — a one-time, dismissible onboarding
tip shown to solo-stage tenants, not a recurring alert.

## What this deliberately doesn't do

- No predictive/forecasting models — every insight is based on data
  that already happened, in past-tense plain language.
- No automatic actions (the advisor never creates a purchase order or
  fires a hiring workflow on its own) — it always ends in a suggestion
  a human decides on.
- No per-tenant custom rules in Phase 1 — the catalog is fixed and
  applies to every tenant the same way. Configurable rules/thresholds
  are a real feature to consider later if tenants ask, not something to
  build speculatively now.
