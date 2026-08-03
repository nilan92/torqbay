# Invoice Template

Generated server-side with **fpdf2** at A4 size, built by
`app/services/invoice_pdf.py` and served by `GET /invoices/{id}/pdf`.

## Why fpdf2, and why not WeasyPrint

WeasyPrint was the original choice — writing the invoice as HTML/CSS is far
pleasanter than positioning text by coordinate. **It cannot run on the
production host.** WeasyPrint needs `libpango` >= 1.44 for
`pango_context_set_round_glyph_positions`; the server has 1.42.3 (build dated
2021) and the account has no root access to upgrade it. Verified by installing
WeasyPrint on the server and attempting a render:

```
AttributeError: function/symbol 'pango_context_set_round_glyph_positions'
not found in library 'libpango-1.0.so.0'
```

fpdf2 is pure Python with no system dependencies, so it has no such exposure.
Benchmarked on the same host: **2.4 ms per invoice, 34 MB resident**. That
speed matters — the account has a hard `LSAPI_CHILDREN` cap of 6 workers, so a
slow render blocks a worker that could be answering other requests.

The cost is that layout is expressed as coordinates rather than CSS. For a
document that must be *precise* and byte-identical regardless of where it was
generated, that is an acceptable trade.

## Why the server renders it, not the app

`expo-print` could produce a PDF on the device, and it would be lighter on the
server. Two reasons it doesn't:

1. **Phase 4 sends invoices over WhatsApp/SMS/email**, on a trigger or a
   schedule, with no phone involved. The server has to be able to produce the
   file by itself.
2. **`expo-print` uses each platform's own rendering engine**, so the same
   invoice comes out subtly different on iOS, Android and web — different font
   substitution, spacing and page breaks. For a tax document a customer keeps,
   one renderer producing one identical file is the point.

The app still owns *viewing*, sharing and printing — it just doesn't build the
file.

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
- **Storage**: none. The PDF is regenerated per request from the invoice
  rows, so there is no `pdf_url` column, no object storage, no signed URLs and
  no orphaned files to clean up after a correction. At 2.4 ms a render this is
  cheaper than storing and invalidating copies. Revisit only if rendering ever
  shows up as real latency.
- **One layout, tenant-branded**: a single builder with the tenant's details
  slotted in is enough for Phase 1. Per-tenant custom templates are a real
  feature request to wait for, not something to build speculatively.

## Data needed at render time

Everything is already on `invoices` + `invoice_line_items` + `tenants` +
`customers` + `assets` (see [data model doc](03-data-model.md)) — no
extra tables needed just for invoicing.
