---
name: odoo-addon-workflow
description: Safe lifecycle for our Odoo 20 addons — create, install, upgrade, dry-run data on the vela_test DB, apply to CommercePulse, verify logs and result. Use whenever installing/upgrading an addon, running a loader/migration script, or changing models, views, data or assets in addons/.
---

# Odoo addon workflow

Golden rule: **`vela_test` first, `CommercePulse` second, verify third.**

## 0. Know what kind of change it is

| Change | Needs |
|---|---|
| Python logic only | `docker compose restart odoo` |
| New/changed field, model, view, data XML, manifest | `-u <addon>` |
| JS/SCSS assets | `-u <addon>` (or run with `--dev=assets` while iterating) |
| New addon | `-i <addon>` |

## 1. Verify the v20 API before coding

```bash
docker compose exec -T odoo grep -rn "<symbol>" /usr/lib/python3/dist-packages/odoo/addons/<module>
```

## 2. Dry-run on vela_test

Install/upgrade (server can keep running, different DB):
```bash
docker compose run --rm --no-deps odoo odoo -d vela_test -u <addon> --stop-after-init 2>&1 \
  | grep -E "WARNING|ERROR|CRITICAL|Traceback" | head -40
```

Script / loader dry-run with rollback (nothing persists):
```python
# script.py, piped into: docker compose run --rm --no-deps -T odoo odoo shell -d vela_test --no-http < script.py
from odoo.addons.<addon>.<module> import <fn>
<fn>(env)
print(<checks>)
env.cr.rollback()
```

If `vela_test` is missing or polluted, recreate it:
```bash
docker compose exec -T db dropdb -U odoo --if-exists --force vela_test
./scripts/setup.sh vela_test        # same bootstrap the teammate uses: identical to CommercePulse
```

After any change, follow `rules/reproducibility.md`: `./scripts/drift.sh` must report no drift.

## 3. Apply to CommercePulse

```bash
./scripts/backup.sh CommercePulse            # only if the owner wants a backup for this change
docker compose stop odoo
docker compose run --rm --no-deps odoo odoo -d CommercePulse -u <addon> --stop-after-init 2>&1 \
  | grep -E "WARNING|ERROR|CRITICAL|Traceback" | head -40
docker compose start odoo
```

## 4. Verify

- `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8069/web/login` → 200
- `docker compose logs --since 2m odoo | grep -E "ERROR|Traceback"` → empty
- Check the actual result: a query, the page in the browser, or a screenshot.
- Report what was verified and what wasn't.

## Pitfalls we hit

- Odoo 20 binary fields want a base64 **str**, not bytes.
- The Buy route can't be set on products. Warehouse `buy_to_resupply` handles it.
- A `grep -c` with no matches exits 1, so don't treat that as a failed install.
- Long Commons/network jobs can hang after the laptop sleeps. Use timeouts.
