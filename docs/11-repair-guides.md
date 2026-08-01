# Repair Guides

An in-app reference so a technician mid-job can quickly find "how do I
remove/install this part on this vehicle model" — video or written steps,
surfaced right from the job/part they're working on instead of them
switching apps to search YouTube.

## Key design decision: shared across tenants, not tenant-scoped

Every other table in this app is tenant-owned (see [data model doc](03-data-model.md)).
This one deliberately isn't: how to remove a Toyota Corolla's front bumper
doesn't differ between workshops, so the guide library is a **shared,
platform-level resource** every tenant reads from and can contribute to —
the value compounds as more tenants use the app, instead of every
workshop rebuilding the same reference alone.

## What it is NOT (scope discipline)

- **Not a video hosting platform.** Guides link to existing video content
  (YouTube, manufacturer channels) rather than the app storing/streaming
  video itself — avoids real infrastructure cost and complexity for
  something an existing platform already solves well. A technician taps
  a guide, it opens YouTube (in-app WebView or a deep link to the YouTube
  app) — no custom video player to build or maintain.
- **Not authoritative/official instructions.** These are reference
  material, not a substitute for a manufacturer service manual — see the
  liability note below.

## Data model

Platform-level table (not tenant-scoped, unlike the convention in
[the data model doc](03-data-model.md)):

### `repair_guides`

| Field | Notes |
|---|---|
| id | PK |
| asset_type | `vehicle` / `electronics` / `appliance` (matches `assets.type`) |
| make, model | e.g. `Toyota`, `Corolla` |
| year_from, year_to | nullable — a guide can apply to a range or be year-agnostic |
| component | e.g. `front bumper`, `brake pads`, `alternator` — free text, matched against inventory item names/job descriptions for search |
| title | e.g. "Removing the front bumper — Corolla 2014-2019" |
| video_url | external link (YouTube etc.), nullable |
| steps | optional written steps, plain text/markdown |
| source | `youtube` / `manufacturer_manual` / `workshop_contributed` |
| contributed_by_tenant_id | nullable FK — which tenant submitted it, if any |
| is_verified | platform admin reviewed and approved it for wider visibility |
| created_at | |

## Contribution flow

Any technician/owner can submit a guide (a link + a note) from within the
app — crowdsourced the same way a shared wiki grows. New submissions
default to `is_verified = false` and are visible to the contributing
tenant immediately, but only surfaced to *other* tenants once a platform
admin marks them verified — a lightweight moderation gate rather than a
full review workflow, since the point is catching spam/wrong content, not
gatekeeping every submission.

## Liability note

Guides are informational, sourced from public videos/manuals or other
technicians' notes — not the platform's own certified instructions. Show
a small, permanent disclaimer on the guide screen ("Reference only —
verify against your vehicle's specifics") rather than presenting guides
as authoritative repair procedures. This is a real liability
consideration, not boilerplate legal text — get it in front of a lawyer
before launch if the guide library sees real usage, same as any
user-generated-content feature would need.

## In-app surfacing

No new bottom tab — a full "Guides" tab would clutter the navigation for
a feature that's only relevant mid-job (see the
[straightforward-over-powerful principle](05-mobile-app.md)). Instead:

- **From job detail**: a "Need help?" button next to the asset info,
  pre-filtered by that job's `asset.type`/`make`/`model`.
- **From add-a-part flow**: tapping a part while adding it to a job shows
  "Guides for this part on [vehicle model]" if any exist — the exact
  moment a technician would want it.
- **Search fallback**: a simple search screen (asset type, make, model,
  component) reachable from the job detail's "Need help?" button, for
  when there's no exact match to the job's own part list.

## API

- `GET /repair-guides?asset_type=&make=&model=&year=&component=` — search, verified guides + the requesting tenant's own unverified submissions
- `POST /repair-guides` — contribute a guide (any authenticated staff role)
- `PATCH /admin/repair-guides/{id}/verify` — platform admin only

## Phasing

Independent of payments, notifications, and AI features — pure content +
search, no external integration risk. See [roadmap](08-roadmap.md) for
where it sits in build order.
