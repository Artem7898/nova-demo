# Changelog

## Unreleased

- Extend the Railway profile to PostgreSQL with required connection variables and
  an optional full-demo check that requires Redis/Memcached configuration.
- Add a production-container CI job exercising all 19 scenarios through HTTP on
  PostgreSQL, Redis and Memcached, including HTTPS proxy handling and CSRF.
- Serve uploaded product images only to the owning visitor workspace or staff;
  protect media in development and production with the same access checks.
- Document the full Railway Hobby deployment and a $15 monthly spending limit,
  with a $10 alert, private service connections and billing limitations.

- Railway Free deployment profile: a Docker image with locked runtime dependencies,
  one synchronous Gunicorn worker, automatic PORT binding and SQLite on a volume.
- Production-only HTTPS/proxy settings, secure cookies, explicit allowed hosts and
  startup checks for a private secret and persistent storage.
- Lightweight database readiness endpoint `/healthz/` and startup migrations after
  volume mounting. Tests cover real HTTP, RU/EN and database survival after restart.
- Railway setup and usage-limit documentation; CI builds and checks the Docker image.

## 0.2.1 — 2026-09-22

- RU/EN switch in the upper panel: native Django i18n, CSRF protection,
  save the language for a year and return to the current page/script.
- English translations of templates, scripts, checks, application errors, and JS.
  User data and API IDs do not change.
- Separate stable group IDs preserve scenario filtering
  regardless of the translated titles.
- Added query language checks, sandbox and data preservation, CSRF,
local redirect, and a real JS catalog in DOM tests.
- Compiled translations are included in the delivery. The Django Nova version remains 0.6.3.

## 0.2.0 — 2026-09-21

- New interface: laboratory, catalog, diagrams, integrations, SVG illustrations,
  mobile navigation, input presets, and JSON result export.
- 19 scenarios use the published django-nova 0.6.3 without monkeypatch.
- Fixed lifecycle task engine, dual assignment, DRF create/PATCH,
negative price checks and optional services.
- Added session sandboxes and operation restrictions; CSRF protects as well
  anonymous entries via DRF. Admin requires staff authorization.
- Cache hit is confirmed by null SQL. Commit/rollback and connections are checked,
  the independence of returned objects, TTL, and the change of remote generations.
- The scheduler uses an abstract read projection: the proxy model does not prevent Nova
from determining the dependencies of cached tables.
- Local OpenTelometry exporter with explicit sampling, limited buffer and no
sending of traces to a third party. A separate example is Nova Metrics.
- FastAPI: compilation and OpenAPI. GraphQL: a limited experimental query.
  Migrations: SQL preview only. These scripts do not provide production guarantees.
- SQLite quickstart, Compose for PostgreSQL/Redis/Memcached, lock file,
  API and script checks, CI, migration instructions, and data cleanup.
