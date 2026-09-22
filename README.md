# Nova Demo — interactive dogfooding lab

Interactive Django application for checking **published django-nova 0.6.3**.
Demo version — **0.2.1**. This is a separate project, not an update of the Nova package sources.

The lab contains 19 executable scripts, a CRUD catalog, a schema inspector,
connection statuses, a Swagger UI, and a closed Django Admin. Interface in Russian and English (RU / EN),
adaptive grid, keyboard navigation, JSON editor, error presets,
SQL counters and export of startup results. The catalog images are local SVG.
Fonts are downloaded from Google Fonts; if there is no network, the system font is used.

## Hosting on Railway

For all 19 demo scenarios, use [Railway Hobby with PostgreSQL, Redis and Memcached](docs/railway-hobby.md).
The guide targets a budget up to $15/month and documents usage alerts and the
workspace hard limit. The final cost depends on actual consumption.

For a minimal starter, follow the [Railway Free deployment guide](docs/railway.md) for the Docker image,
persistent SQLite volume, HTTPS, healthcheck and RU/EN verification. The single-service
profile leaves the three Redis/Memcached scenarios explicitly skipped. Railway's
free usage allowance is limited; enable Serverless and check account usage.

## Quick Launch: SQLite

We need Python 3.12 and uv. Unzip the archive into a separate folder:

```bash
cd nova-demo
uv sync --locked --all-extras --dev
uv run --locked manage.py migrate
uv run --locked manage.py runserver
```

Open **http://127.0.0.1:8000 /**. The first entry creates your sandbox:
8 products and 3 categories. You don't need an account. Each browser session sees
its own records; the administrative part remains accessible only to staff.

Click "Run all checks". Without Redis/Memcached, three scripts will receive the status
"Skipped" with connection instructions. FastAPI and GraphQL are installed via
`--all-extras`; without extras, their scripts are also explicitly skipped.

Open "Demo" catalog → "Create product" for CRUD. A negative price will give an error
Nova, and the correct entry will appear in your sandbox. In Swagger, visit
the main page first: it creates a session and a CSRF cookie. POST/PATCH/DELETE requests
require the `X-CSRFToken` header. The catalog interface sends it automatically.

## Interface language

The **RU / EN** switch is located on the right in the upper panel on all public
pages. The selection is stored in a cookie for a year and is valid for navigation,
scripts, test results, and interface messages. Changing the language returns
to the current page with the same URL parameters and saves the session sandbox.
Product names and other user data are not translated.
The browser language is taken into account before the first selection; the backup language is Russian.

Changing the language reloads the page: blank forms and launch history,
The information stored only in the memory of the current page is reset. The saved items
remain in the database. Swagger and low-level messages from external libraries can
remain in English.

The translations are in `locale/en/LC_MESSAGES/`. Ready-made `.mo` files are included in the archive —
no installation is required to run gettext. After editing the `.po`
, rebuild them (the command requires GNU gettext):

```bash
uv run --locked manage.py compilemessages -l en \
  --ignore .venv --ignore node_modules --ignore staticfiles
uv run --locked pytest -q tests/test_i18n.py
```

Restart Django when updating a working installation. If the static
is served via the WhiteNoise/production server, run
`uv run --locked manage.py collectstatic --noinput`. There are no new migrations for RU/EN.

## PostgreSQL + Redis + Memcached

Compose uses ports 5433, 56379, and 51211, which are bound to localhost.
The test passwords from Compose are only suitable for the local demo.

```bash
docker compose up -d --wait
export NOVA_DEMO_DB=postgres
export PGHOST=127.0.0.1
export PGPORT=5433
export PGDATABASE=nova_demo
export PGUSER=nova
export PGPASSWORD=nova
export NOVA_DEMO_REDIS_URL=redis://127.0.0.1:56379/0
export NOVA_DEMO_MEMCACHED_SERVER=127.0.0.1:51211
uv run --locked manage.py migrate
uv run --locked manage.py runserver
```

The alternative: copy `.env.example` to `.env`, fill in the values and use
`uv run --locked --env-file .env manage.py ...`for **each** team.
The settings do not automatically read `.env`.

Stop: `docker compose down'. The volume `pgdata' is saved. Do not use `down -v'
if you want to save PostgreSQL.

## Checks

```bash
uv run --locked pyright catalog config
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked manage.py check
uv run --locked manage.py makemigrations --check --dry-run
uv run --locked pytest -q -rs -W error::pytest.PytestWarning
uv run --locked manage.py nova_smoke --require-services
uv run --locked manage.py collectstatic --noinput
uv run --locked manage.py spectacular --validate --file /tmp/nova-demo-api.yaml
```

For DOM checks of the interface, a Node is needed.js 20+: `npm ci --ignore-scripts && npm test`.
They use real Django templates and responses, but they are not a substitute for visual browser validation.
For the normal launch of the Node website.js is not required.

`nova_smoke` accesses the configured database and real services. A normal run
without `--require-services` resolves the absence of optional services; an unsuccessful
check always terminates the command with a non-zero code. The entire pytest uses a separate
test database; the Postgres user needs CREATEDB permission. For SQLite, this is a temporary database.
CI runs an SQLite/PostgreSQL matrix with Redis and Memcached.

In "Tasks & retry", the first exception is called specifically. Message
`failed, retrying 1/1` in the log is expected: the final check requires SUCCESS and exactly
two attempts. This is a queue in the current process, completed before the HTTP response, not
a long-lasting distributed queue.

## Updating an existing demo

1. Save your folder and make a backup copy of the database/media.
2. Expand the new version next to it. Migrate your connection variables, media and
, if necessary, SQLite. The new quickstart uses `demo.sqlite3` rather than
   old `db.sqlite3`: the old file is not automatically replaced.
3. For the old PostgreSQL, specify the same NAME/USER/HOST/PORT and execute `migrate`.
4. Migrations 0001-0005 are saved. New ones add workspace and metadata; old ones
   The categories remain with workspace=NULL, are visible in Admin and are not given to visitors.
5. Previous monkeypatch files `catalog/nova_compat.py `and `catalog/bridge.py ` more
   not used. Do not copy them to the new version.

For the old SQLite, you can copy **a backup copy** of `db.sqlite3` under the name
`demo.sqlite3` to a new folder and perform migrate. Do not replace an already filled one
`demo.sqlite3` without a separate decision on data migration.

## Public demonstration

Before publishing, set up a separate database, HTTPS, `DJANGO_DEBUG=0`, your own
`DJANGO_SECRET_KEY', `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS'.
The application does not contain a user login to Admin: create an administrator
via `uv run --locked manage.py createsuperuser`. Do not publish his password.

```bash
uv run --locked manage.py collectstatic --noinput
uv run --locked gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 1 --threads 1 --timeout 60
```

Set up a reverse proxy with HTTPS and a shared rate limit. Built-in demo restrictions
(60 launches/min/IP, 120 API requests/min/IP, 50 products, 12 categories, 30 reports)
they do not replace the protection of a public service. The built-in throttle and memory cache are local
to the process; write limits are not designed to counter a competitive attack.
With multiple processes, an external write can disable the cache at the same
time as the demo check of the HIT — this result requires a restart.
Use PostgreSQL for concurrent users.

Sessions last 24 hours; delete outdated sandboxes on a schedule:

```bash
uv run --locked manage.py prune_demo --days 7 --dry-run
uv run --locked manage.py prune_demo --days 7
uv run --locked manage.py clearsessions
```

The cleanup only affects DemoWorkspace and related records. The categories of the previous
directory with workspace=NULL are not deleted. The scripts do not invoke FLUSHDB/FLUSHALL;
the deleted keys have a unique namespace. Do not connect the production cache to the demo.
'NOVA_DEMO_ALLOW_RUNS=0` disables the lab; the catalog continues to work.

## What exactly is being demonstrated

See [scenario map](docs/CAPABILITIES.md), [interface verification](docs/UI-CHECKLIST.md)
, and [results of verification of this delivery](docs/VERIFICATION.md).
GraphQL remains an experiment. SQL migrations are shown without DDL execution.
Measurements in the UI include monitoring tools and are not a substitute for performance benchmarks.
The serialization/GC stage of the main django-nova remains a separate task.
