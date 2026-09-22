# Full Nova Demo on Railway Hobby — budget up to $15/month

Use this profile to run all 19 current demo scenarios against real PostgreSQL,
Redis and Memcached. FastAPI remains an OpenAPI projection, GraphQL remains an
experimental read-only query, and the migration card previews SQL without DDL.
The hosting plan does not change those documented boundaries.

## 1. Set the budget before provisioning

Choose **Hobby** in a workspace dedicated to this demo. Hobby costs at least
$5/month and includes $5 of resource usage: a $12 usage bill totals $12 before
applicable taxes, not $17. Pro is not required.

In **Workspace → Usage → Set Usage Limits**, configure **Compute Usage**:

- Custom email alert: **$10**.
- Hard limit: **$15** if that also fits the final billed total. If taxes or payment
  conversion apply, lower the compute limit to leave room within the $15 budget.
- Do not enable additional paid products or Railway Agent usage for this setup.
  Agent Usage is metered and capped separately from Compute Usage.

The hard limit applies to the whole workspace. At the threshold Railway takes
workloads offline; it does not promise a full month of uptime within $15. Check
the projected bill after 24–48 hours and reduce usage if it exceeds the budget.
Do not raise the cap automatically. Keep GitHub deployments on one environment;
preview copies also consume resources.

Sources, checked 2026-09-22: [pricing](https://railway.com/pricing),
[billing rules](https://docs.railway.com/pricing/plans),
[cost controls](https://docs.railway.com/pricing/cost-control).

## 2. Create four services in one project and region

| Service name | Source | Persistence / networking |
| --- | --- | --- |
| `nova-demo` | GitHub `Artem7898/nova-demo`, branch `main` | Volume at `/data`; public HTTPS domain |
| `Postgres` | Railway PostgreSQL template | Keep its database volume; private connection |
| `Redis` | Railway Redis template | Keep template authentication; private connection |
| `Memcached` | Docker image `memcached:1.6-alpine` | No volume; private port 11211 |

Service names in this table match the variable references below. Railway GitHub
deployment does not execute the local `docker-compose.yml`: create these services
in the dashboard. Do not create public TCP proxies for databases/caches.

For Memcached, use this start command:

```text
memcached -m 32 -c 128 -t 1 -U 0
```

It uses a 32 MB item cache, one worker thread, and no UDP listener. Total process
memory is higher than the item cache. Keep it on the private project network.
The optional services page in the demo reports connection status.

## 3. Configure the web service

The root Dockerfile installs all adapter extras and collects static assets.
Leave custom build/start/pre-deploy commands empty. The container migrates the
database at startup, then launches one synchronous Gunicorn worker.

Attach the web volume at `/data` for uploaded images. Railway supplies its mount
path automatically. PostgreSQL data belongs to the separate Postgres volume.

Add these variables to **nova-demo → Variables → Raw Editor**:

```dotenv
DJANGO_DEBUG=0
NOVA_DEMO_DB=postgres
NOVA_DEMO_REQUIRE_SERVICES=1
NOVA_DEMO_ALLOW_RUNS=1
PGHOST=${{Postgres.RAILWAY_PRIVATE_DOMAIN}}
PGPORT=5432
PGDATABASE=${{Postgres.PGDATABASE}}
PGUSER=${{Postgres.PGUSER}}
PGPASSWORD=${{Postgres.PGPASSWORD}}
NOVA_DEMO_REDIS_URL=${{Redis.REDIS_URL}}
NOVA_DEMO_MEMCACHED_SERVER=${{Memcached.RAILWAY_PRIVATE_DOMAIN}}:11211
PORT=8000
```

Confirm the Redis URL references its private hostname and preserves its template
password. Generate a private `DJANGO_SECRET_KEY` locally and add it separately:

```bash
uv run --locked python -c 'import secrets; print(secrets.token_urlsafe(64))'
```

Paste directly into Railway; do not commit it or send it in chat. Keep the same
secret on later deployments so existing sessions remain valid.

Set healthcheck **`/healthz/`**, timeout **120 seconds**, and **one replica**.
Generate a public domain targeting **8000**; the application trusts the supplied
`RAILWAY_PUBLIC_DOMAIN` and Railway's HTTPS proxy. Redeploy after domain changes.
Enable **Serverless** for the web service to reduce idle costs, accepting cold
starts. Do not depend on database/cache sleeping to meet the budget.

The full profile rejects missing database/cache settings. Readiness checks the
database; `/lab/api/health/` also checks Redis and Memcached. Watch all four
services become healthy before testing the application.

## 4. Verify the deployed site

1. Open the generated HTTPS URL; check the catalog and RU/EN switching.
2. In Integrations, confirm PostgreSQL, Redis and Memcached are ready.
3. Run all checks: expect **19 passed**, with no skipped service scenarios.
4. Create a catalog entry, refresh, and verify session isolation in another browser.
5. Restart the web service; the first browser should keep its catalog.
6. Inspect usage and memory graphs, then check the monthly cost projection.

CI runs the production Docker image with PostgreSQL, Redis and Memcached and
executes all 19 scenarios through HTTP, including CSRF-protected requests. It also
tests SQLite as a separate starter configuration. Passing CI does not verify the
Railway account's billing settings or an actual Railway deployment.

## Media and maintenance

Uploaded product images are served by Django only to the owning workspace or
staff. Unregistered files, active document types such as SVG, and another
visitor's images return 404. Bundled catalog SVG assets remain public static files.
The existing catalog API does not add a new upload form; staff can upload through
the existing Django Admin. No public staff account is created.

Run these manually through the service shell before scheduling cleanup:

```bash
python manage.py prune_demo --days 7 --dry-run
python manage.py prune_demo --days 7
python manage.py clearsessions
```

Cleanup deletes old demo workspaces. Back up data before changes and monitor the
media volume separately: deleting model rows does not automatically delete every
uploaded file. Do not migrate a deployed SQLite database by merely switching the
environment variable: export/import its data explicitly if it contains anything
that should be preserved.
