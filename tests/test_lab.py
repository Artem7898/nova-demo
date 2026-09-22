import os

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, override_settings
from nova.cache import get_default_cache

from catalog.lab.registry import SCENARIOS
from catalog.lab.runner import adapters_installed, run_scenario
from catalog.models import Category, Product, Tag

CORE = [
    s["id"]
    for s in SCENARIOS
    if s["id"] not in ("redis", "redis_tools", "memcached", "fastapi", "graphql")
]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("scenario", CORE)
def test_experiments_execute_and_clean_up(scenario):
    before = (Category.objects.count(), Product.objects.count(), Tag.objects.count())
    result = run_scenario(scenario)
    assert result["status"] == "passed", result
    assert result["checks"] and all(c["passed"] for c in result["checks"])
    assert before == (Category.objects.count(), Product.objects.count(), Tag.objects.count())


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("scenario", ["fastapi", "graphql"])
def test_optional_adapters(scenario):
    result = run_scenario(scenario)
    assert result["status"] == ("passed" if adapters_installed() else "skipped"), result


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "payload", [{"name": "OK name", "price": "-1"}, {"name": "", "price": "12"}]
)
def test_rejected_values_do_not_persist(payload):
    result = run_scenario("validation", payload)
    assert result["status"] == "passed", result
    assert result["output"]["outcome"] == "rejected"
    assert not result["output"]["persisted"]
    assert not Product.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_bad_planner_input_is_failed_not_passed():
    result = run_scenario("planner", {"rows": 999})
    assert result["status"] == "failed"
    assert result["output"]["error_type"] == "ValueError"


@pytest.mark.parametrize("scenario", ["redis", "redis_tools", "memcached"])
@override_settings(NOVA_DEMO_REDIS_URL="", NOVA_DEMO_MEMCACHED_SERVER="")
def test_missing_services_are_explicitly_skipped(scenario):
    assert run_scenario(scenario)["status"] == "skipped"


@pytest.mark.integration
@pytest.mark.parametrize(
    "scenario,env",
    [
        ("redis", "NOVA_DEMO_REDIS_URL"),
        ("redis_tools", "NOVA_DEMO_REDIS_URL"),
        ("memcached", "NOVA_DEMO_MEMCACHED_SERVER"),
    ],
)
def test_real_services(scenario, env):
    if not os.getenv(env):
        pytest.skip(f"Set {env} to run against a real service")
    result = run_scenario(scenario)
    assert result["status"] == "passed", result


@pytest.mark.django_db(transaction=True)
def test_lab_http_csrf_input_and_cache():
    c = Client(enforce_csrf_checks=True)
    assert c.get("/").status_code == 200
    assert (
        c.post("/lab/api/run/cache/", data="{}", content_type="application/json").status_code == 403
    )
    token = {"HTTP_X_CSRFTOKEN": c.cookies["csrftoken"].value}
    assert c.get("/lab/api/run/cache/").status_code == 405
    for body in ("[1]", "invalid"):
        assert (
            c.post(
                "/lab/api/run/cache/", data=body, content_type="application/json", **token
            ).status_code
            == 400
        )
    assert (
        c.post(
            "/lab/api/run/cache/", data="x" * 17000, content_type="application/json", **token
        ).status_code
        == 413
    )
    assert (
        c.post(
            "/lab/api/run/unknown/", data="{}", content_type="application/json", **token
        ).status_code
        == 404
    )
    result = c.post(
        "/lab/api/run/cache/", data="{}", content_type="application/json", **token
    ).json()
    assert result["status"] == "passed", result
    assert result["steps"][1]["sql_count"] == 0
    with override_settings(NOVA_DEMO_ALLOW_RUNS=False):
        assert (
            c.post(
                "/lab/api/run/cache/", data="{}", content_type="application/json", **token
            ).status_code
            == 403
        )
    cache.clear()
    get_default_cache().clear()


@pytest.mark.django_db(transaction=True)
def test_cleanup_command_preserves_original_catalog():
    from datetime import timedelta

    from django.utils import timezone

    from catalog.models import DemoWorkspace
    from catalog.workspaces import seed_workspace

    old = seed_workspace(DemoWorkspace.objects.create())
    DemoWorkspace.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=10))
    keep = Category.objects.create(name="Original data", slug="original")
    call_command("prune_demo", days=7, dry_run=True)
    assert DemoWorkspace.objects.filter(pk=old.pk).exists()
    call_command("prune_demo", days=7)
    assert not DemoWorkspace.objects.filter(pk=old.pk).exists()
    assert Category.objects.filter(pk=keep.pk).exists()


@pytest.mark.integration
@pytest.mark.django_db
def test_remote_health_checks_use_live_services(client):
    if not all(os.getenv(name) for name in ("NOVA_DEMO_REDIS_URL", "NOVA_DEMO_MEMCACHED_SERVER")):
        pytest.skip("Configure both remote services")
    services = client.get("/lab/api/health/").json()["services"]
    assert services["redis"]["status"] == services["memcached"]["status"] == "ready"
