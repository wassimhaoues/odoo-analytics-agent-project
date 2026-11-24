# Infra & commands

All commands run from the repo root.

| Task | Command |
|---|---|
| Start / stop | `docker compose up -d` / `docker compose stop` |
| Logs | `docker compose logs -f --tail=100 odoo` |
| Restart after Python change | `docker compose restart odoo` |
| Install/upgrade addon (real DB) | `docker compose stop odoo && docker compose run --rm --no-deps odoo odoo -d CommercePulse -u <addon> --stop-after-init && docker compose start odoo` |
| Same on test DB (server can keep running) | `docker compose run --rm --no-deps odoo odoo -d vela_test -u <addon> --stop-after-init` |
| Odoo shell | `docker compose run --rm --no-deps -T odoo odoo shell -d <db> --no-http < script.py` |
| SQL | `docker compose exec -T db psql -U odoo -d <db>` |
| Read Odoo source | `docker compose exec -T odoo grep -rn "<x>" /usr/lib/python3/dist-packages/odoo/addons/<mod>` |
| Backup / restore | `./scripts/backup.sh <db>` / `./scripts/restore.sh backups/<dir> [newdb]` |
| Reset test DB | `docker compose exec -T db dropdb -U odoo --force vela_test` then `./scripts/setup.sh vela_test` |

## Facts

- Odoo listens on `127.0.0.1:8069` only, and `dbfilter = ^CommercePulse$` pins HTTP to the real DB. `vela_test` is CLI-only (a second DB without the filter makes every page redirect to the DB selector). Postgres has **no host port** (5432 belongs to
  another project on this machine). Other local containers (redis, mongo, seaweedfs) belong
  to other projects. Don't touch them.
- Volumes `odoo-db-data`, `odoo-web-data` hold all real data. Never `docker compose down -v`.
- `vela_analytics` → Kafka: `VELA_DELIVERY_MODE` (`local` default | `bridge`), `VELA_BRIDGE_URL`,
  `VELA_BRIDGE_TOKEN` in `.env`, passed to the Odoo container by docker-compose. After changing
  them: `docker compose up -d odoo` (recreates the container; restart alone keeps old env).
- Step 3 services (Kafka, Spark, HDFS) go in `pipeline/docker-compose.yml` with their own
  `.env` keys, joined to the Odoo network. Mind RAM: start only what a task needs.
