import importlib.metadata
import json
import time

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from nova.cache import get_default_cache
from nova.validation.pydantic_bridge import generate_pydantic_schema

from .lab.registry import SCENARIO_MAP, SCENARIOS
from .lab.runner import adapters_installed, run_scenario
from .models import Category, Product, Report, Tag
from .workspaces import get_workspace


def runtime_context(request):
    return {
        "nova_version": importlib.metadata.version("django-nova"),
        "django_version": importlib.metadata.version("django"),
        "database_vendor": connection.vendor,
        "scenario_count": len(SCENARIOS),
    }


def catalog_payload(workspace):
    return [
        {"id": c.pk, "name": c.name}
        for c in Category.objects.filter(workspace=workspace).order_by("name")
    ]


@ensure_csrf_cookie
def home(request):
    get_workspace(request)
    return render(request, "lab.html", {"page": "lab", "scenarios": SCENARIOS})


@ensure_csrf_cookie
def catalog(request):
    workspace = get_workspace(request)
    qs = (
        Product.objects.filter(category__workspace=workspace)
        .select_related("category")
        .order_by("id")
    )
    q = request.GET.get("q", "")[:200]
    qs = qs.filter(name__icontains=q) if q else qs
    selected = request.GET.get("category", "")
    if selected.isdigit():
        qs = qs.filter(category_id=int(selected))
    page = Paginator(qs, 8).get_page(request.GET.get("page"))
    return render(
        request,
        "catalog/product_list.html",
        {
            "page": "catalog",
            "products": page,
            "categories": catalog_payload(workspace),
            "query": q,
            "selected_category": selected,
            "total_products": Product.objects.filter(category__workspace=workspace).count(),
        },
    )


def product_detail(request, pk):
    workspace = get_workspace(request)
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("tags", "photos"),
        pk=pk,
        category__workspace=workspace,
    )
    return render(request, "catalog/product_detail.html", {"page": "catalog", "product": product})


@ensure_csrf_cookie
def schemas(request):
    return render(request, "schemas.html", {"page": "schemas"})


@ensure_csrf_cookie
def integrations(request):
    return render(request, "integrations.html", {"page": "integrations", "scenarios": SCENARIOS})


@require_GET
def schema_data(request, model):
    models = {"product": Product, "category": Category, "tag": Tag, "report": Report}
    if model not in models:
        return JsonResponse({"detail": "Unknown model"}, status=404)
    cls = models[model]
    canonical = cls._nova_config.pydantic_schema or generate_pydantic_schema(cls)
    return JsonResponse(
        {
            "model": cls._meta.label,
            "schema": canonical.model_json_schema(),
            "fields": [
                {
                    "name": f.name,
                    "type": type(f).__name__,
                    "nullable": f.null,
                    "primary_key": f.primary_key,
                }
                for f in cls._meta.concrete_fields
            ],
        }
    )


@require_GET
def health(request):
    services = {
        "database": {"status": "ready", "label": connection.vendor},
        "memory": {"status": "ready", "label": "Process-local cache"},
        "redis": {"status": "not_configured", "label": "Redis"},
        "memcached": {"status": "not_configured", "label": "Memcached"},
    }
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        services["database"]["status"] = "unavailable"
    if settings.NOVA_DEMO_REDIS_URL:
        import redis

        try:
            with redis.Redis.from_url(
                settings.NOVA_DEMO_REDIS_URL, socket_timeout=0.5, socket_connect_timeout=0.5
            ) as client:
                services["redis"]["status"] = "ready" if client.ping() else "unavailable"
        except Exception:
            services["redis"]["status"] = "unavailable"
    if settings.NOVA_DEMO_MEMCACHED_SERVER:
        from pymemcache.client.base import Client

        try:
            host, port = settings.NOVA_DEMO_MEMCACHED_SERVER.rsplit(":", 1)
            client = Client((host, int(port)), timeout=0.5, connect_timeout=0.5)
            try:
                services["memcached"]["status"] = "ready" if client.version() else "unavailable"
            finally:
                client.close()
        except Exception:
            services["memcached"]["status"] = "unavailable"
    return JsonResponse(
        {
            "version": importlib.metadata.version("django-nova"),
            "services": services,
            "adapters": adapters_installed(),
            "runs_enabled": settings.NOVA_DEMO_ALLOW_RUNS,
        }
    )


@require_POST
def run_lab(request, scenario_id):
    if not settings.NOVA_DEMO_ALLOW_RUNS:
        return JsonResponse({"detail": gettext("Запуск сценариев отключён.")}, status=403)
    if scenario_id not in SCENARIO_MAP:
        return JsonResponse({"detail": "Unknown scenario"}, status=404)
    if len(request.body) > 16_384:
        return JsonResponse({"detail": gettext("Максимум 16 КБ JSON.")}, status=413)
    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"detail": gettext("Некорректный JSON.")}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"detail": gettext("Ожидается JSON-объект.")}, status=400)
    bucket = f"demo-run:{request.META.get('REMOTE_ADDR')}:{int(time.time()) // 60}"
    cache.add(bucket, 0, timeout=65)
    if cache.incr(bucket) > 60:
        return JsonResponse(
            {"detail": gettext("Лимит: 60 сценариев в минуту. Подождите.")}, status=429
        )
    return JsonResponse(run_scenario(scenario_id, payload))


@require_GET
def cache_stats(request):
    return JsonResponse(
        {"backend": "memory", "scope": "process", "stats": get_default_cache().get_stats()}
    )
