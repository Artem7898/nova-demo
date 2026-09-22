"""Every card names an executable scenario and its actual boundary."""

from django.utils.translation import gettext_lazy

GROUP_LABELS = {
    "basics": gettext_lazy("Основы"),
    "performance": gettext_lazy("Производительность"),
    "consistency": gettext_lazy("Согласованность"),
    "execution": gettext_lazy("Выполнение"),
    "adapters": gettext_lazy("Адаптеры"),
    "observability": gettext_lazy("Наблюдаемость"),
    "infrastructure": gettext_lazy("Инфраструктура"),
}


def scenario(id, title, group, description, code, payload=None, *, requirement=None, mode="live"):
    return {
        "id": id,
        "title": title,
        "group": GROUP_LABELS[group],
        "group_id": group,
        "description": description,
        "code": code,
        "payload": payload or {},
        "requirement": requirement,
        "mode": mode,
    }


SCENARIOS = [
    scenario(
        "validation",
        gettext_lazy("Валидация модели"),
        "basics",
        gettext_lazy("Измените цену или название. Nova проверит данные до записи в БД."),
        "product = Product(**payload)\nproduct.save()  # Pydantic → Django → clean → constraints",
        {"name": "Studio Headphones", "price": "129.00"},
    ),
    scenario(
        "serialization",
        gettext_lazy("Сериализация"),
        "basics",
        gettext_lazy("Несохранённая модель, JSON, файл 4 КБ и преобразование Django ↔ Pydantic."),
        'product.to_dict()\nproduct.to_pydantic().model_dump(mode="json")',
    ),
    scenario(
        "planner",
        gettext_lazy("Планировщик запросов"),
        "performance",
        gettext_lazy("Сравните N+1 и план Nova на одинаковых моделях и связях."),
        "plan = build_query_plan(ProductReadPlan)\noptimized = apply_plan(queryset, plan)",
        {"rows": 5},
    ),
    scenario(
        "cache",
        "Cache hit / miss",
        "performance",
        gettext_lazy("Два чтения одного запроса: реальные SQL-счётчики и время каждого шага."),
        "cache.get_or_set(queryset)  # miss\ncache.get_or_set(queryset)  # hit",
    ),
    scenario(
        "invalidation",
        gettext_lazy("Commit и rollback"),
        "consistency",
        gettext_lazy("Изменение станет видимым после commit; rollback сохранит прежнее значение."),
        "with transaction.atomic():\n    product.save()\n# invalidation runs on_commit",
    ),
    scenario(
        "relations",
        gettext_lazy("Связанные модели"),
        "consistency",
        gettext_lazy("Изменение категории обновляет кэш запроса с select_related."),
        'category.name = "Updated"\ncategory.save()\ncache.get_or_set(queryset.select_related("category"))',
    ),
    scenario(
        "isolation",
        gettext_lazy("Изоляция результата"),
        "consistency",
        gettext_lazy("Изменение списка, модели, JSON и связи не должно менять сохранённый кэш."),
        'rows = cache.get_or_set(queryset)\nrows[0].metadata["specs"]["edition"] = "changed"\nfresh = cache.get_or_set(queryset)',
    ),
    scenario(
        "context",
        "Async context",
        "execution",
        gettext_lazy("Вложенные области, параллельные задачи и восстановление после исключения."),
        'with new_context(request_id="outer"):\n    await asyncio.gather(worker("A"), worker("B"))',
    ),
    scenario(
        "async_orm",
        "Async ORM",
        "execution",
        gettext_lazy("Настоящее асинхронное чтение модели через aget и aexists."),
        "product = await Product.objects.aget(pk=product_id)\nexists = await Product.objects.filter(pk=product_id).aexists()",
    ),
    scenario(
        "tasks",
        "Task engine & retry",
        "execution",
        gettext_lazy(
            "Изолированный engine: очередь, контролируемый сбой, повтор и результат. Завершается в запросе."
        ),
        "await engine.start()\nid = engine.submit(work, max_retries=1)\nawait engine.stop()\nengine.get_status(id)",
    ),
    scenario(
        "drf",
        "DRF adapter",
        "adapters",
        gettext_lazy(
            "Сгенерированный сериализатор: create, PATCH и отклонение отрицательной цены."
        ),
        "Serializer = to_drf_serializer(Product)\nserializer.is_valid(raise_exception=True)\nserializer.save()",
    ),
    scenario(
        "admin",
        "Admin compiler",
        "adapters",
        gettext_lazy("Схема формы и реальная проверка формы, собранной compile_admin."),
        "Admin = compile_admin(Category)\nui_schema = get_admin_schema(Category)",
    ),
    scenario(
        "tracing",
        "Tracing & metrics",
        "observability",
        gettext_lazy("Настоящий OpenTelemetry span и события локального экспортера Nova Metrics."),
        'with nova_span("demo.read"):\n    registry.increment("demo.reads")',
    ),
    scenario(
        "redis",
        "Redis backend",
        "infrastructure",
        gettext_lazy("Round-trip, TTL и смена общего поколения на настоящем Redis."),
        "backend.set(key, value, ttl=30)\nbackend.rotate_generation(scope)",
        requirement="redis",
    ),
    scenario(
        "redis_tools",
        "Locks, rate limit, Pub/Sub",
        "infrastructure",
        gettext_lazy("Конкурирующие блокировки, лимит запросов и доставка сообщения через Redis."),
        "await lock.acquire()\ncheck_rate_limit(key, limit=2, window_secs=10)\nawait bus.publish(event)",
        requirement="redis",
    ),
    scenario(
        "memcached",
        "Memcached backend",
        "infrastructure",
        gettext_lazy("Независимое хранение, TTL и общие поколения на настоящем Memcached."),
        "backend.set(key, value, ttl=30)\nbackend.get(key)\nbackend.rotate_generation(scope)",
        requirement="memcached",
    ),
    scenario(
        "fastapi",
        "FastAPI projection",
        "adapters",
        gettext_lazy("Сборка роутера Nova и OpenAPI через ASGI. CRUD показан отдельно в DRF."),
        'app.include_router(to_fastapi_router(Category, prefix="/categories"))',
        requirement="adapters",
        mode="preview",
    ),
    scenario(
        "graphql",
        "GraphQL projection",
        "adapters",
        gettext_lazy(
            "Эксперимент: Strawberry-тип из Pydantic и выполнение ограниченного read-only запроса."
        ),
        'GraphType = to_strawberry_type(schema=CategoryRead)\nschema.execute_sync("{ example { name } }")',
        requirement="adapters",
        mode="experimental",
    ),
    scenario(
        "migrations",
        gettext_lazy("Миграции и routing"),
        "infrastructure",
        gettext_lazy(
            "Просмотр SQL CreateIndexConcurrently и состояния маршрутизатора. DDL и репликация не выполняются."
        ),
        "operation = CreateIndexConcurrently(...)\nprint(operation.sql)",
        mode="preview",
    ),
]
SCENARIO_MAP = {s["id"]: s for s in SCENARIOS}
