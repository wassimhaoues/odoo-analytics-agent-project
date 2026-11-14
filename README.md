# Odoo Analytics Agent Project

Study project: an Odoo 20 eCommerce test website, a custom analytics addon that tracks
visitor behaviour, a big-data pipeline (Kafka, Spark, Hadoop), and an AI agent addon
(voice + text) that reads the analytics, talks to the shop owner and performs actions.

## Roadmap

1. **eCommerce website**: Odoo Website + eCommerce, plus a custom theme/data addon
2. **Analytics addon** (`addons/website_analytics`): page views, clicks, sessions, cart events
3. **Big data pipeline** (`pipeline/`): Kafka ingestion → Spark processing → HDFS storage
4. **AI agent addon** (`addons/ai_marketing_agent`): voice/text agent with analytics tools and actions

## Layout

```
docker-compose.yml   Odoo 20 + Postgres 17 (pipeline services added later)
.env.example         secrets template -> copy to .env
config/              odoo.conf (git-ignored) + odoo.conf.example
addons/              custom Odoo addons (mounted at /mnt/extra-addons)
pipeline/            Kafka / Spark / Hadoop code and configs
docs/                specs and design notes
scripts/             backup.sh / restore.sh
backups/             local DB backups (git-ignored)
```

## Setup

```bash
cp .env.example .env                              # set POSTGRES_PASSWORD
cp config/odoo.conf.example config/odoo.conf      # set admin_passwd
docker compose up -d
```

Open http://localhost:8069

## Backups

```bash
./scripts/backup.sh <dbname>
./scripts/restore.sh backups/<db>-<timestamp> [new_dbname]
```
