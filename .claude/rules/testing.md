# Testing & verification

## Levels

1. **Static**: `python3 -m py_compile` on Python, XML well-formed (the `edit-lint` hook does both).
2. **Dry-run**: run the change on `vela_test` first. For data loaders, run inside
   `odoo shell` and `env.cr.rollback()` at the end (see `odoo-addon-workflow`).
3. **Odoo tests**: `tests/test_*.py` using `TransactionCase` (model logic) or `HttpCase`
   (controllers, tours). Tag them: `@tagged("post_install", "-at_install", "vela")`.
   Run on the test DB:
   ```bash
   docker compose run --rm --no-deps odoo odoo -d vela_test -u <addon> \
     --test-enable --test-tags /<addon> --stop-after-init --no-http
   ```
4. **Visual**: for UI, screenshots at 375/768/1440 px, light + dark, reduced-motion
   (Chrome DevTools emulation), keyboard-only pass. Then the `ui-critic` agent.

## What needs a test (ponytail rule)

New non-trivial logic: a branch, a parser, money, security, an event endpoint, an AI tool.
Trivial view/markup changes need the visual check instead.

## Reporting

Say exactly what ran and what didn't. "Tests pass" only if you ran them in this session.
