# Invoice Template

Generated server-side with **WeasyPrint** (renders an HTML/CSS template to
PDF) at A4 size, triggered by `POST /jobs/{id}/invoice`. One Jinja2
template file: `app/templates/invoice/invoice.html`.

## Why HTML/CSS instead of a PDF-drawing library

WeasyPrint takes a normal HTML+CSS document and rasterizes it to PDF, so
"make it look nice" is a CSS/layout problem (something any web-capable
dev can do quickly) instead of manually placing text boxes and lines with
a low-level library like ReportLab. `@page { size: A4; margin: ... }`
handles the page format directly.

## Layout (top to bottom)

1. **Header band**: workshop logo (top-left, from `tenants.logo_url`),
   workshop name/address/phone/email (top-right), and — since this is
   Sri Lanka — the Business Registration Number and VAT Registration
   Number if the tenant is VAT-registered (`tenants.vat_registration_number`
   nullable, omit the line entirely if not set)
2. **Invoice meta row**: Invoice # (`invoice_number`), issue date, due
   date, status badge (draft/sent/paid — colored)
3. **Bill-to block**: customer name, phone, address; asset info (e.g.
   vehicle plate/model) so the invoice ties clearly to the serviced item
4. **Line items table**: description, quantity, unit price, line total —
   labor lines and part lines both flow through the same
   `invoice_line_items` table (`type` field distinguishes them for
   reporting, not for display)
5. **Totals block**: Subtotal → Tax (rate % shown explicitly, e.g. "VAT
   18%") → Total, right-aligned, total in bold/larger type
6. **Payment info footer**: bank details or accepted payment methods text
   (tenant-configurable, stored on `tenants` or a small settings blob),
   plus a thank-you line
7. **Footer**: page number, generated-by-app watermark line (small, grey)

## Practical rules

- **Currency formatting**: `LKR 12,500.00` — comma thousands separator,
  2 decimals, matches local convention (see [localization doc](07-sri-lanka-localization.md))
- **Numbering**: `invoice_number` is tenant-scoped sequential
  (`INV-2026-0001`), generated at invoice creation time inside a DB
  transaction to avoid race-condition duplicates under concurrent creates
- **Immutability**: once an invoice is `sent`, line items are not
  editable — corrections go through a credit note or a new invoice, not
  an edit. (Prevents a paid PDF a customer already has from silently
  disagreeing with what's in the database.)
- **Storage**: rendered PDF saved to object storage, `pdf_url` on the
  invoice row is a signed, expiring link — not a public URL
- **One template, tenant-branded**: a single HTML template with the
  tenant's logo/colors slotted in is enough for Phase 1. Per-tenant custom
  templates are a real feature request to wait for, not something to
  build speculatively.

## Data needed at render time

Everything is already on `invoices` + `invoice_line_items` + `tenants` +
`customers` + `assets` (see [data model doc](03-data-model.md)) — no
extra tables needed just for invoicing.
