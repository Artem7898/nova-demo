"""Bounded experiments using the installed Nova package, with observable checks."""

import asyncio
import importlib.util
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, cast

from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import connection, connections, transaction
from django.utils.translation import gettext
from nova.cache import get_default_cache
from nova.core import context
from nova.core.exceptions import NovaValidationError
from nova.query.planner import apply_plan, build_query_plan

from catalog.models import Category, Product, ProductReadPlan, Tag
from catalog.tasks import execute_report

from .registry import SCENARIO_MAP


class Unavailable(Exception):
    pass


class Observation:
    def __init__(self):
        self.steps = []
        self.checks = []

    def check(self, condition, label):
        self.checks.append({"label": label, "passed": bool(condition)})
        if not condition:
            raise AssertionError(label)

    def measure(self, label, fn):
        count = 0
        sql_ms = 0.0

        def wrapper(execute, sql, params, many, execution_context):
            nonlocal count, sql_ms
            start = time.perf_counter()
            try:
                return execute(sql, params, many, execution_context)
            finally:
                count += 1
                sql_ms += (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        try:
            with connection.execute_wrapper(wrapper):
                return fn()
        finally:
            self.steps.append(
                {
                    "label": label,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 3),
                    "sql_count": count,
                    "sql_ms": round(sql_ms, 3),
                }
            )


@contextmanager
def dataset(rows=3):
    slug = uuid.uuid4().hex
    category = Category.objects.create(name="Lab category", slug=f"lab-{slug}")
    tag = None
    try:
        tag = Tag.objects.create(name=f"Lab-{slug}")
        products = []
        for i in range(rows):
            product = Product.objects.create(
                category=category,
                name=f"Lab product {i + 1}",
                price=Decimal("129.00"),
                metadata={"specs": {"edition": "2026"}},
            )
            product.tags.add(tag)
            products.append(product)
        yield category, products
    finally:
        category.delete()
        if tag is not None:
            tag.delete()


def require_service(name):
    value = getattr(settings, f"NOVA_DEMO_{name.upper()}_{'URL' if name == 'redis' else 'SERVER'}")
    if not value:
        raise Unavailable(
            gettext("Настройте {variable} и запустите сервис.").format(
                variable=f"NOVA_DEMO_{name.upper()}_{'URL' if name == 'redis' else 'SERVER'}"
            )
        )
    return value


def validation(obs, payload):
    with dataset(0) as (category, _):
        name = payload.get("name", "Studio Headphones")
        price = payload.get("price", "129.00")
        if not isinstance(name, str) or not isinstance(price, (str, int, float)):
            raise ValueError(gettext("name должен быть строкой, price — строкой или числом."))
        product = Product(category=category, name=name, price=price)
        try:
            obs.measure("NovaModel.save()", product.save)
        except NovaValidationError as exc:
            obs.check(product.pk is None, gettext("Невалидная модель не записана в БД"))
            return {
                "outcome": "rejected",
                "message": str(exc),
                "details": exc.details,
                "persisted": False,
            }
        obs.check(product.pk is not None, gettext("Валидная модель записана"))
        obs.check(isinstance(product.price, Decimal), gettext("Цена нормализована в Decimal"))
        return {
            "outcome": "accepted",
            "data": product.to_dict(),
            "price_type": type(product.price).__name__,
            "persisted": True,
        }


def serialization(obs, payload):
    with dataset(0) as (category, _):
        product = Product(
            category=category, name="Unsaved product", price="49.00", metadata={"nested": [1, 2]}
        )
        product.preview = ContentFile(b"x" * 4096, name="preview.png")
        result = obs.measure(
            "to_dict → to_pydantic", lambda: product.to_pydantic().model_dump(mode="json")
        )
        obs.check(
            result["preview"] == "preview.png",
            gettext("Файл сериализован по имени, не по длине содержимого"),
        )
        obs.check(product.pk is None, gettext("Сериализация не сохраняет модель"))
        from nova.validation.pydantic_bridge import model_to_pydantic, pydantic_to_model

        restored = cast(Category, pydantic_to_model(Category, model_to_pydantic(category)))
        obs.check(
            restored.name == category.name, gettext("Django → Pydantic → Django сохраняет данные")
        )
        return {
            "serialized": result,
            "file_bytes": 4096,
            "unsaved_m2m_access": "excluded by canonical schema",
            "roundtrip": restored.name,
        }


def planner(obs, payload):
    rows = payload.get("rows", 5)
    if isinstance(rows, bool) or not isinstance(rows, int) or not 1 <= rows <= 12:
        raise ValueError(gettext("rows должен быть целым числом от 1 до 12"))
    with dataset(rows) as (category, _):
        qs = Product.objects.filter(category=category).order_by("id")

        def project(queryset):
            return [
                {
                    "name": p.name,
                    "price": str(p.price),
                    "category": p.category.name,
                    "tags": [t.name for t in p.tags.all()],
                }
                for p in queryset
            ]

        baseline = obs.measure(gettext("Обычный ORM"), lambda: project(qs.all()))
        plan = build_query_plan(ProductReadPlan)
        optimized = obs.measure(gettext("План Nova"), lambda: project(apply_plan(qs.all(), plan)))
        obs.check(baseline == optimized, gettext("Результаты обоих запросов совпадают"))
        obs.check(
            obs.steps[1]["sql_count"] < obs.steps[0]["sql_count"], gettext("План устраняет N+1")
        )
        return {"plan": plan.explain(), "rows": len(optimized), "sample": optimized[0]}


def cache(obs, payload):
    with dataset() as (category, _):
        qcache = get_default_cache()
        qs = Product.objects.filter(category=category).order_by("id")
        first = obs.measure(gettext("MISS · чтение из БД"), lambda: qcache.get_or_set(qs))
        second = obs.measure(gettext("HIT · чтение из кэша"), lambda: qcache.get_or_set(qs))
        obs.check(obs.steps[0]["sql_count"] > 0, gettext("Первое чтение выполняет SQL"))
        obs.check(obs.steps[1]["sql_count"] == 0, gettext("Повторное чтение не выполняет SQL"))
        obs.check(
            [p.pk for p in first] == [p.pk for p in second],
            gettext("Содержимое результатов совпадает"),
        )
        return {
            "backend": "memory",
            "rows": len(second),
            "cache_scope": "process",
            "ttl_seconds": qcache.get_stats()["ttl"],
        }


def invalidation(obs, payload):
    with dataset(1) as (category, products):
        product = products[0]
        qcache = get_default_cache()
        qs = Product.objects.filter(category=category)
        qcache.get_or_set(qs)
        with transaction.atomic():
            product.price = Decimal("149.00")
            product.save()
        fresh = obs.measure(gettext("Чтение после COMMIT"), lambda: qcache.get_or_set(qs))
        obs.check(
            fresh[0].price == Decimal("149.00"), gettext("Commit делает новое значение видимым")
        )
        with transaction.atomic():
            product.price = Decimal("999.00")
            product.save()
            transaction.set_rollback(True)
        after = obs.measure(gettext("Чтение после ROLLBACK"), lambda: qcache.get_or_set(qs))
        obs.check(
            after[0].price == Decimal("149.00"), gettext("Rollback не публикует отменённую цену")
        )
        obs.check(obs.steps[1]["sql_count"] == 0, gettext("Rollback сохраняет прежний cache hit"))
        return {"committed_price": str(fresh[0].price), "after_rollback": str(after[0].price)}


def relations(obs, payload):
    with dataset(1) as (category, _):
        qs = Product.objects.filter(category=category).select_related("category")
        qcache = get_default_cache()
        old = qcache.get_or_set(qs)
        obs.measure(gettext("HIT до изменения связи"), lambda: qcache.get_or_set(qs))
        obs.check(
            obs.steps[-1]["sql_count"] == 0, gettext("Исходный результат действительно кэширован")
        )
        category.name = "Updated category"
        category.save()
        new = obs.measure(gettext("Чтение после category.save()"), lambda: qcache.get_or_set(qs))
        obs.check(
            new[0].category.name == "Updated category",
            gettext("Связанная модель инвалидирует результат"),
        )
        return {"before": old[0].category.name, "after": new[0].category.name}


def isolation(obs, payload):
    with dataset(1) as (category, _):
        qs = (
            Product.objects.filter(category=category)
            .select_related("category")
            .prefetch_related("tags")
        )
        qcache = get_default_cache()
        rows = qcache.get_or_set(qs)
        original_name = rows[0].name
        original_tag = rows[0].tags.all()[0].name
        rows[0].name = "Changed outside cache"
        rows[0].metadata["specs"]["edition"] = "changed"
        rows[0].category.name = "Changed category"
        rows[0].tags.all()[0].name = "Changed tag"
        rows.clear()
        fresh = obs.measure(gettext("Независимое повторное чтение"), lambda: qcache.get_or_set(qs))
        obs.check(obs.steps[-1]["sql_count"] == 0, gettext("Повторное чтение получено из кэша"))
        obs.check(len(fresh) == 1, gettext("Изменение списка не затронуло кэш"))
        obs.check(fresh[0].name == original_name, gettext("Модель изолирована"))
        obs.check(
            fresh[0].metadata["specs"]["edition"] == "2026", gettext("Вложенный JSON изолирован")
        )
        obs.check(fresh[0].category.name == "Lab category", gettext("select_related изолирован"))
        obs.check(
            fresh[0].tags.all()[0].name == original_tag, gettext("prefetch_related изолирован")
        )
        return {
            "list": True,
            "model": True,
            "json": True,
            "select_related": True,
            "prefetch_related": True,
        }


def context_demo(obs, payload):
    async def run():
        initial = context.get_all()

        async def worker(value):
            with context.new_context(worker=value):
                await asyncio.sleep(0)
                return context.get_all()

        with context.new_context(request_id="outer"):
            siblings = await asyncio.gather(worker("A"), worker("B"))
            try:
                with context.new_context(request_id="inner"):
                    raise ValueError("Controlled failure")
            except ValueError:
                restored = context.get_all()
            started = asyncio.Event()

            async def cancellable():
                with context.new_context(worker="cancelled"):
                    started.set()
                    await asyncio.Future()

            task = asyncio.create_task(cancellable())
            await started.wait()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            after_cancel = context.get_all()
        return initial, siblings, restored, after_cancel, context.get_all()

    initial, siblings, restored, after_cancel, final = obs.measure(
        "Async scopes", lambda: asyncio.run(run())
    )
    obs.check(
        siblings == [{"worker": "A"}, {"worker": "B"}], gettext("Параллельные задачи изолированы")
    )
    obs.check(
        restored == after_cancel == {"request_id": "outer"},
        gettext("Исключение и отмена не меняют внешний контекст"),
    )
    obs.check(initial == final, gettext("Исходный контекст восстановлен"))
    return {"tasks": siblings, "after_exception": restored, "after_cancel": after_cancel}


def async_orm(obs, payload):
    with dataset(1) as (_, products):

        async def read():
            try:
                obj = await Product.objects.aget(pk=products[0].pk)
                exists = await Product.objects.filter(pk=obj.pk).aexists()
                return obj.name, exists
            finally:
                await sync_to_async(connections.close_all, thread_sensitive=True)()

        name, exists = obs.measure("aget + aexists", lambda: async_to_sync(read)())
        obs.check(
            exists and name == products[0].name, gettext("Async ORM возвращает сохранённую модель")
        )
        return {
            "name": name,
            "exists": exists,
            "sql_note": gettext(
                "SQL работает в worker-потоке; счётчик текущего потока его не включает."
            ),
        }


def tasks(obs, payload):
    result = obs.measure(
        "Engine → controlled retry → success",
        lambda: async_to_sync(execute_report)([Decimal("10"), Decimal("20")], retry=True),
    )
    obs.check(result["status"] == "SUCCESS", gettext("Задача завершилась успешно"))
    obs.check(
        result["result"]["attempts"] == 2, gettext("После контролируемого сбоя был один повтор")
    )
    return {"task": result, "scope": "in-process, workers stopped before response"}


def drf(obs, payload):
    from nova.ecosystem.drf import to_drf_serializer

    Serializer = to_drf_serializer(Product)
    with dataset(0) as (category, _):
        create = Serializer(data={"name": "DRF product", "price": "45.50", "category": category.pk})
        obs.check(
            create.is_valid(),
            gettext("Create валиден: {errors}").format(errors=dict(create.errors)),
        )
        product = obs.measure("DRF create → NovaModel.save", create.save)
        patch = Serializer(product, data={"price": "46.00"}, partial=True)
        obs.check(patch.is_valid(), gettext("PATCH валидирует объединённое состояние"))
        obs.measure("DRF PATCH", patch.save)
        invalid = Serializer(product, data={"price": "-1"}, partial=True)
        obs.check(not invalid.is_valid(), gettext("Сериализатор отклоняет отрицательную цену"))
        return {
            "created_id": product.pk,
            "patched_price": str(product.price),
            "invalid_errors": invalid.errors,
        }


def admin_demo(obs, payload):
    from nova.admin.api import compile_admin, get_admin_schema

    Admin = compile_admin(Category)
    form = Admin.form(data={"name": "Valid name", "slug": f"form-{uuid.uuid4().hex}"})
    obs.check(
        form.is_valid(),
        gettext("Сгенерированная форма принимает валидные данные: {errors}").format(
            errors=dict(form.errors)
        ),
    )
    invalid = Admin.form(data={"name": "", "slug": ""})
    obs.check(not invalid.is_valid(), gettext("Сгенерированная форма отклоняет пустые поля"))
    return {
        "admin_class": Admin.__name__,
        "ui_schema": get_admin_schema(Category),
        "errors": invalid.errors.get_json_data(),
    }


def tracing(obs, payload):
    from nova.core.tracing import nova_span
    from nova.metrics.exporters import MetricsExporter
    from nova.metrics.registry import MetricsRegistry

    from catalog.telemetry import exporter

    events = []

    class Exporter(MetricsExporter):
        def increment(self, metric, value):
            events.append({"metric": metric, "value": value})

        def timing(self, metric, duration_ms):
            events.append({"metric": metric, "duration_ms": duration_ms})

    registry = MetricsRegistry()
    registry.register_exporter(Exporter())
    token = uuid.uuid4().hex
    with nova_span("demo.read", demo_run=token) as span:
        registry.increment("demo.reads")
        registry.timing("demo.latency", 1.25)
        active = span is not None and span.is_recording()
    spans = exporter.for_run(token)
    obs.check(active and bool(spans), gettext("OpenTelemetry записал и экспортировал span"))
    obs.check(len(events) == 2, gettext("Nova Metrics доставил counter и timing"))
    return {
        "spans": spans,
        "metrics": events,
        "timing_note": gettext(
            "1.25 ms — вход примера API timing, не измерение производительности."
        ),
    }


def remote_cache(obs, payload, kind):
    from nova.cache.generation import generation_key

    token = f"demo:{uuid.uuid4().hex}"
    if kind == "redis":
        import redis
        from nova.cache.backends.redis import RedisCacheBackend

        client = redis.Redis.from_url(
            require_service(kind), socket_timeout=1, socket_connect_timeout=1
        )
        client.ping()
        backend = RedisCacheBackend(client=client, key_prefix=token)
    else:
        from nova.cache.backends.memcached import MemcachedCacheBackend
        from pymemcache.client.base import Client

        host, port = require_service(kind).rsplit(":", 1)
        client = Client((host, int(port)), connect_timeout=1, timeout=1, default_noreply=False)
        client.version()
        backend = MemcachedCacheBackend(client=client)
    key = token + ":value"
    try:
        value = {"nested": [1, 2]}
        obs.measure(gettext("Запись с TTL"), lambda: backend.set(key, value, ttl=30))
        value["nested"].append(3)
        saved = obs.measure(gettext("Чтение из удалённого backend"), lambda: backend.get(key))
        obs.check(saved == {"nested": [1, 2]}, gettext("Сериализованное значение не изменилось"))
        before = backend.get_generation(token)
        after = backend.rotate_generation(token)
        obs.check(
            before != after and backend.get_generation(token) == after,
            gettext("Общее поколение сменилось"),
        )
        backend.set(key, "expired", ttl=0)
        obs.check(backend.get(key) is None, gettext("TTL=0 удаляет значение"))
        return {
            "backend": kind,
            "real_service": True,
            "generation_changed": True,
            "ttl_zero": "expired",
        }
    finally:
        backend.delete(key)
        backend.delete(generation_key(token))
        client.close()


def redis_demo(obs, payload):
    return remote_cache(obs, payload, "redis")


def memcached_demo(obs, payload):
    return remote_cache(obs, payload, "memcached")


def redis_tools(obs, payload):
    url = require_service("redis")

    async def run():
        from nova.core.exceptions import NovaRateLimitError
        from nova.redis.locks import AsyncDistributedLock
        from nova.redis.pubsub import AsyncNovaPubSub
        from nova.redis.rate_limiter import async_check_rate_limit
        from redis.asyncio import Redis

        client = Redis.from_url(url, socket_timeout=2, socket_connect_timeout=1)
        token = f"demo:{uuid.uuid4().hex}"
        a = AsyncDistributedLock(token, timeout=5, blocking_timeout=0, client=client)
        b = AsyncDistributedLock(token, timeout=5, blocking_timeout=0, client=client)
        stream = None
        pending = None
        try:
            first = await a.acquire()
            blocked = not await b.acquire()
            await a.release()
            reacquired = await b.acquire()
            await b.release()
            allowed = [await async_check_rate_limit(token, 2, 10, client=client) for _ in range(2)]
            try:
                await async_check_rate_limit(token, 2, 10, client=client)
            except NovaRateLimitError:
                limited = True
            else:
                limited = False
            bus = AsyncNovaPubSub(token, client=client)
            stream = cast(AsyncGenerator[dict[str, Any], None], bus.listen())

            async def receive():
                return await anext(stream)

            pending = asyncio.create_task(receive())

            async def deliver():
                while not (await client.pubsub_numsub(bus.channel_name))[0][1]:
                    await asyncio.sleep(0.01)
                await bus.publish({"event": "demo", "run": token})
                return await pending

            message = await asyncio.wait_for(deliver(), timeout=3)
            return {
                "lock": [first, blocked, reacquired],
                "allowed": allowed,
                "limited": limited,
                "message": message,
            }
        finally:
            if pending is not None and not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            if stream is not None:
                await stream.aclose()
            await a.release()
            await b.release()
            await client.delete(f"nova:rl:{token}")
            await client.aclose()

    result = obs.measure("Redis utilities", lambda: asyncio.run(run()))
    obs.check(
        all(result["lock"]), gettext("Блокировка не допускает второго владельца и освобождается")
    )
    obs.check(result["limited"], gettext("Третий запрос отклонён rate limiter"))
    obs.check(result["message"]["event"] == "demo", gettext("Pub/Sub доставил сообщение"))
    return result


def adapters_installed():
    return all(
        importlib.util.find_spec(name) is not None for name in ("fastapi", "strawberry", "httpx")
    )


def fastapi_demo(obs, payload):
    if not adapters_installed():
        raise Unavailable(gettext("Выполните uv sync --locked --all-extras --dev"))
    import httpx
    from fastapi import APIRouter, FastAPI
    from nova.ecosystem.fastapi import to_fastapi_router

    # Compile a model projection, then inspect OpenAPI. A public in-process list
    # must never expose categories from another visitor, so no ORM request is issued.
    app = FastAPI()
    app.include_router(cast(APIRouter, to_fastapi_router(Category, prefix="/categories")))

    async def read_schema():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://demo"
        ) as client:
            return await client.get("/openapi.json")

    response = obs.measure("ASGI GET /openapi.json", lambda: async_to_sync(read_schema)())
    data = response.json()
    methods = list(data["paths"]["/categories/"])
    obs.check(
        response.status_code == 200 and "get" in methods and "post" in methods,
        gettext("Роутер публикует GET/POST контракт"),
    )
    return {
        "routes": data["paths"],
        "boundary": "OpenAPI projection only; catalog CRUD is demonstrated via DRF.",
    }


def graphql_demo(obs, payload):
    if not adapters_installed():
        raise Unavailable(gettext("Выполните uv sync --locked --all-extras --dev"))
    import strawberry
    from nova.ecosystem.graphql import to_strawberry_type
    from pydantic import BaseModel

    class ExampleContract(BaseModel):
        name: str

    GraphType = to_strawberry_type(schema=ExampleContract)

    def example():
        return GraphType(name="Django Nova")

    example.__annotations__["return"] = GraphType
    Query = strawberry.type(type("Query", (), {"example": strawberry.field(resolver=example)}))
    schema = strawberry.Schema(query=Query)
    result = obs.measure(
        "GraphQL execute_sync", lambda: schema.execute_sync("{ example { name } }")
    )
    obs.check(
        result.errors is None and result.data["example"]["name"] == "Django Nova",
        gettext("Скалярная проекция выполняется"),
    )
    return {
        "query": "{ example { name } }",
        "data": result.data,
        "sdl": schema.as_str(),
        "status": "experimental, no API stability claim",
    }


def migrations(obs, payload):
    from nova.db.router import NovaDatabaseRouter, replica_state
    from nova.db.zero_downtime import CreateIndexConcurrently

    op = CreateIndexConcurrently(
        table="catalog_product", index_name="demo_product_name_idx", columns=["name"]
    )
    router = NovaDatabaseRouter()
    prior = replica_state.should_use_replica()
    try:
        replica_state.set_read_from_replica()
        router.db_for_write(Product)
        cleared = not replica_state.should_use_replica()
    finally:
        if prior:
            replica_state.set_read_from_replica()
        else:
            replica_state.clear_replica_state()
    obs.check("CONCURRENTLY" in op.sql, gettext("Операция генерирует concurrent index SQL"))
    obs.check(cleared, gettext("Запись сбрасывает выбор реплики"))
    return {
        "forward_sql": op.sql,
        "reverse_sql": op.reverse_sql,
        "executed": False,
        "boundary": "Preview only. CREATE INDEX CONCURRENTLY requires PostgreSQL and a non-atomic migration. No replica configured.",
    }


RUNNERS = {
    "validation": validation,
    "serialization": serialization,
    "planner": planner,
    "cache": cache,
    "invalidation": invalidation,
    "relations": relations,
    "isolation": isolation,
    "context": context_demo,
    "async_orm": async_orm,
    "tasks": tasks,
    "drf": drf,
    "admin": admin_demo,
    "tracing": tracing,
    "redis": redis_demo,
    "redis_tools": redis_tools,
    "memcached": memcached_demo,
    "fastapi": fastapi_demo,
    "graphql": graphql_demo,
    "migrations": migrations,
}


def run_scenario(scenario_id, payload=None):
    if scenario_id not in SCENARIO_MAP:
        raise KeyError(scenario_id)
    obs = Observation()
    start = time.perf_counter()
    status = "passed"
    try:
        output = RUNNERS[scenario_id](obs, payload or {})
    except Unavailable as exc:
        status, output = "skipped", {"message": str(exc)}
    except Exception as exc:
        status, output = "failed", {"error_type": type(exc).__name__, "message": str(exc)}
    return {
        "id": scenario_id,
        "run_id": uuid.uuid4().hex[:12],
        "status": status,
        "duration_ms": round((time.perf_counter() - start) * 1000, 3),
        "checks": obs.checks,
        "steps": obs.steps,
        "output": output,
        "measurement_note": "Step timings exclude fixture setup/cleanup. These are observations, not a performance benchmark.",
    }
