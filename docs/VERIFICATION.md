# Delivery verification 0.2.1

Tested on 2026-09-22 on Python 3.12.14, published by django-nova 0.6.3,
Django 5.2.17 and SQLite. For integrations, real Redis 7.4.2 and
Memcached 1.6.39 local processes are running.

| Verification | Result |
|---|---|
| `uv sync --locked --all-extras --dev` | the lock file is consistent |
| `pytest -q -rs -W error::pytest.PytestWarning` with services | **60 passed**, without skipped/warnings |
| `manage.py nova_smoke --require-services` | **19/19 passed** |
| `npm test` | **6 DOM tests passed** |
| `pyright catalog config` | **0 errors, 0 warnings** |
| Ruff check / format --check | passed |
| Django system check | 0 issues |
| makemigrations --check --dry-run | No changes detected |
| spectacular --validate | passed |
| collectstatic | build completed |
| node --check app.js | passed |
| EN / EN: 12 language checks, cookies, data retention, API and CSRF | passed |
| compilemessages: django / djangojs | English `.mo` collected |
| Compose and GitHub workflow | YAML is sorted |

Without configured remote services, four integration pytest tests intentionally
skipped are: Redis backend, Redis utilities, Memcached backend, and shared health.
In the laboratory itself, three cards are skipped without services.

DOM checks use jsdom: Django renders templates in a separate temporary database,
and saved responses are checked in the UI. This is not visual browser testing.
The cloud browser of this environment rejected the local address of the application.
(`ERR_BLOCKED_BY_CLIENT'); desktop/mobile layout should be checked by UI-CHECKLIST.md .

PostgreSQL and Docker Compose did not run in this environment. Prepared for them
the GitHub Actions matrix and the README commands; their successful run is not stated here.
The behavior of published Nova is checked without editing its installed files.