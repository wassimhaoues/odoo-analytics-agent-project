# 0009. Cash on delivery only; VAT on every product; content pages

- Status: accepted
- Date: 2026-11-21

## Context
The site promised "you pay when it arrives", but checkout offered the Demo card provider
and pay-on-site only. The spec puts real payment processing out of scope. Products had no
sales tax although prices are Tunisian retail prices with 19% VAT included. The cookie bar
was off, so the spec's consent gate (FR-01, T2) had nothing to read, and the legal pages were
Odoo placeholders.

## Decision
- **Payments:** no online payment. `vela_setup` switches off every provider (Demo, wire transfer,
  pay on invoice…) except two: it publishes
  *Cash on delivery* (home delivery carriers allow it) and keeps *Pay at pickup* for in-store
  collection. `payment_demo` stays installed (dropping it would need an uninstall step).
- **VAT:** the 19% sale tax is the company default and is set on every physical product;
  prices stay as in the catalog and are shown tax included.
- **Consent:** the cookie bar is on, with our own `/cookie-policy` page.
- **Content:** About, Privacy, Cookie policy, Contact (Odoo placeholder content replaced; vela_theme `views/pages.xml`), terms of sale
  (`vela_setup/data/terms_*.html`, also printed on invoices) and three blog posts. New
  tracking area `page` (`page.<page>.<action>`) for links inside content pages.

## Consequences
Checkout has two offline methods; test orders (spec T3) go through cash on delivery and stay
"pending payment" until the delivery is paid, which is the real-world flow. Existing orders keep
their old taxes.

## Alternatives considered
- Keep the Demo provider for tests: it shows a card form, which contradicts the store's promise.
- Wire transfer: not "pay on delivery".
