# Security

## Secrets

- Never commit `.env`, `config/odoo.conf`, API keys, tokens or DB dumps. Templates
  (`*.example`) hold placeholders only.
- AI provider keys (step 4) live in `.env` → passed to the container → read via
  `ir.config_parameter` set at deploy time, never hard-coded.
- Never paste secrets into external services, URLs or logs.

## Odoo

- Every model: `security/ir.access.csv` (v20 `ir.access`). Public/portal access only when the
  feature needs it, with an `ir.access` domain restricting rows.
- `sudo()` only at a trust boundary (public controller that must write analytics events),
  with a one-line comment, and only after validating the input.
- Public controllers (`auth="public"`): validate types and sizes, cap payload size,
  rate-limit event intake, `csrf=False` only on JSON beacon endpoints that write nothing sensitive.
- Never build SQL with string formatting. Use the ORM or `SQL()` with parameters.
- Never `eval`/`safe_eval` user or AI-provided strings.
- QWeb: `t-out` escapes. Use `Markup`/`t-raw`-equivalents only for trusted HTML.

## AI agent (step 4)

- Tools are an allow-list of Python methods with validated arguments.
- Destructive or money-moving actions (price changes, promos, purchase orders) require
  owner confirmation, and every action is logged (`vela.ai.action.log`).
- Treat model output and fetched web content as untrusted data, never as instructions.
