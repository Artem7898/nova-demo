import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

import pytest
from django.db import OperationalError

from catalog.models import DemoWorkspace

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.django_db
def test_readiness_is_a_database_probe_without_a_visitor(client, django_assert_num_queries):
    with django_assert_num_queries(1):
        response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "no-store" in response["Cache-Control"]
    assert not response.cookies
    assert DemoWorkspace.objects.count() == 0
    with patch("config.health.connection.cursor", side_effect=OperationalError("private detail")):
        failure = client.get("/healthz/")
    assert failure.status_code == 503
    assert failure.json() == {"status": "unavailable"}


def production_env(tmp_path):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("DJANGO_", "NOVA_DEMO_", "RAILWAY_", "PG"))
    }
    env.update(
        DJANGO_SETTINGS_MODULE="config.railway_settings",
        DJANGO_DEBUG="0",
        DJANGO_SECRET_KEY="deployment-tests-only-not-a-production-secret-" * 2,
        NOVA_DEMO_DATA_DIR=str(tmp_path / "data"),
        RAILWAY_PUBLIC_DOMAIN="demo.example",
        PATH=f"{Path(sys.executable).parent}{os.pathsep}{env['PATH']}",
    )
    return env


@pytest.mark.parametrize(
    "fault", ["secret", "volume", "relative_path", "postgres", "database_kind", "remote_services"]
)
def test_production_rejects_unsafe_startup(tmp_path, fault):
    env = production_env(tmp_path)
    if fault == "secret":
        env.pop("DJANGO_SECRET_KEY")
    elif fault == "volume":
        env["RAILWAY_ENVIRONMENT_ID"] = "test-railway-environment"
    elif fault == "relative_path":
        env["NOVA_DEMO_DATA_DIR"] = "data"
    elif fault == "database_kind":
        env["NOVA_DEMO_DB"] = "unknown"
    elif fault == "remote_services":
        env.update(
            NOVA_DEMO_DB="postgres",
            NOVA_DEMO_REQUIRE_SERVICES="1",
            PGDATABASE="demo",
            PGUSER="demo",
            PGPASSWORD="test",
            PGHOST="db",
            PGPORT="5432",
        )
    else:
        env["NOVA_DEMO_DB"] = "postgres"
    result = subprocess.run(
        ["sh", "deploy/start.sh"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=10
    )
    assert result.returncode != 0
    assert not (tmp_path / "data" / "demo.sqlite3").exists()


def test_postgres_profile_uses_configured_service_without_sqlite_fallback(tmp_path):
    env = production_env(tmp_path)
    env.update(
        NOVA_DEMO_DB="postgres",
        NOVA_DEMO_REQUIRE_SERVICES="1",
        PGDATABASE="railway",
        PGUSER="postgres",
        PGPASSWORD="test-not-a-secret",
        PGHOST="postgres.railway.internal",
        PGPORT="5432",
        NOVA_DEMO_REDIS_URL="redis://redis.railway.internal:6379/0",
        NOVA_DEMO_MEMCACHED_SERVER="memcached.railway.internal:11211",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from django.conf import settings; "
            "assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql'; "
            "assert settings.DATABASES['default']['HOST'] == 'postgres.railway.internal'; "
            "assert settings.DATABASES['default']['NAME'] == 'railway'; "
            "assert settings.DATABASES['default']['CONN_MAX_AGE'] == 0",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_production_launcher_http_and_database_survive_restart(tmp_path):
    env = production_env(tmp_path)
    # Match Railway: an attached volume supplies the path automatically.
    env["RAILWAY_ENVIRONMENT_ID"] = "test-railway-environment"
    env["RAILWAY_VOLUME_MOUNT_PATH"] = str(tmp_path / "volume")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        env["PORT"] = str(sock.getsockname()[1])
    build_env = {**env, "DJANGO_SETTINGS_MODULE": "config.settings", "DJANGO_DEBUG": "1"}
    subprocess.run(
        [sys.executable, "manage.py", "collectstatic", "--noinput"],
        cwd=ROOT,
        env=build_env,
        check=True,
        capture_output=True,
        timeout=30,
    )
    url = f"http://127.0.0.1:{env['PORT']}"
    database = tmp_path / "volume" / "demo.sqlite3"
    workspace_ids = []
    for attempt in range(2):
        with (tmp_path / f"server-{attempt}.log").open("w+") as log:
            server = subprocess.Popen(
                ["sh", "deploy/start.sh"], cwd=ROOT, env=env, stdout=log, stderr=log
            )
            try:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        request = Request(
                            url + "/healthz/", headers={"Host": "healthcheck.railway.app"}
                        )
                        with urlopen(request, timeout=1) as response:
                            assert json.load(response) == {"status": "ok"}
                        break
                    except OSError:
                        if server.poll() is not None or time.monotonic() >= deadline:
                            log.seek(0)
                            pytest.fail(log.read())
                        time.sleep(0.1)
                with sqlite3.connect(database) as db:
                    assert (
                        db.execute("SELECT id FROM catalog_demoworkspace").fetchall()
                        == workspace_ids
                    )
                if attempt == 0:
                    subprocess.run(
                        [sys.executable, "deploy/check_http.py", url],
                        cwd=ROOT,
                        check=True,
                        timeout=30,
                    )
                    with sqlite3.connect(database) as db:
                        workspace_ids = db.execute(
                            "SELECT id FROM catalog_demoworkspace"
                        ).fetchall()
                    assert len(workspace_ids) == 1
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
