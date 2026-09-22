"""Railway deployment: SQLite starter or PostgreSQL with remote cache services."""

import os
from pathlib import Path

from .settings import *  # noqa: F403

DEBUG = False
if not SECRET_KEY or SECRET_KEY.startswith("local-nova-demo"):  # noqa: F405
    raise RuntimeError("Set a private DJANGO_SECRET_KEY before deployment")
database_kind = os.getenv("NOVA_DEMO_DB", "sqlite")
if database_kind not in {"sqlite", "postgres"}:
    raise RuntimeError("NOVA_DEMO_DB must be sqlite or postgres")
if database_kind == "postgres":
    required = ("PGDATABASE", "PGUSER", "PGPASSWORD", "PGHOST", "PGPORT")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Configure PostgreSQL variables: " + ", ".join(missing))
    DATABASES["default"]["OPTIONS"] = {"connect_timeout": 5}  # noqa: F405

if os.getenv("NOVA_DEMO_REQUIRE_SERVICES", "0") == "1":
    if database_kind != "postgres":
        raise RuntimeError("The full demo profile requires PostgreSQL")
    if not NOVA_DEMO_REDIS_URL or not NOVA_DEMO_MEMCACHED_SERVER:  # noqa: F405
        raise RuntimeError("Configure NOVA_DEMO_REDIS_URL and NOVA_DEMO_MEMCACHED_SERVER")

volume_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")
if os.getenv("RAILWAY_ENVIRONMENT_ID") and not volume_path:
    raise RuntimeError("Attach a Railway volume for persistent database/media storage")
data_path = volume_path or os.getenv("NOVA_DEMO_DATA_DIR", "")
if not data_path or not Path(data_path).is_absolute():
    raise RuntimeError("Set an absolute NOVA_DEMO_DATA_DIR or attach a Railway volume")
DATA_DIR = Path(data_path)
if database_kind == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": DATA_DIR / "demo.sqlite3",
            "OPTIONS": {"timeout": 20},
        }
    }
MEDIA_ROOT = DATA_DIR / "media"

ALLOWED_HOSTS = [*ALLOWED_HOSTS, "healthcheck.railway.app"]  # noqa: F405
public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
if public_domain:
    ALLOWED_HOSTS.append(public_domain)
    CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, f"https://{public_domain}"]  # noqa: F405

# This profile runs behind Railway's HTTPS proxy, not on an untrusted direct port.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
LANGUAGE_COOKIE_SECURE = True
