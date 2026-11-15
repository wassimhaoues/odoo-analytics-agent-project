# 0001. One monorepo; Odoo source stays in the Docker image

- Status: accepted
- Date: 2026-11-14

## Context
The project spans an Odoo store, custom addons, a Kafka/Spark/Hadoop pipeline and an AI
agent. All parts share contracts (tracking events, product SKUs). Odoo itself runs from the
official `odoo:20.0` image with Postgres 17.

## Decision
One git repository holds compose files, config templates, our addons, pipeline code,
scripts and docs. Odoo source is not vendored: it is read from the image when needed.
Secrets live in a git-ignored `.env` and `config/odoo.conf`; `*.example` templates are committed.
HTTP is pinned to the real DB with `dbfilter = ^CommercePulse$`; `vela_test` is used from the CLI only.

## Consequences
Contracts change atomically across parts. Upgrading Odoo means bumping the image tag.
We must verify v20 APIs against the image, not docs for older versions.

## Alternatives considered
- Repo per component: contracts drift, more overhead for one developer.
- Vendoring Odoo source: huge repo, no benefit while we don't patch core.
