# Scenario map

| Scenario | What is being performed | Border |
|---|---|---|
| Model validation | NovaModel.save, Pydantic, Django clean, Decimal | Temporary recordings |
| Serialization | to_dict, to_pydantic, Django↔Pydantic, file 4096 B | File by name, without uploading to disk; M2M excluded from canonical schema |
| Scheduler | build_query_plan/apply_plan, SQL before/after | Abstract projection with category/tags; N+1 vs 2 queries |
| Cache hit/miss | Two get_or_sets, SQL counters | Memory, within the process |
| Commit/rollback | Real atomic blocks and on_commit | A consistent scenario |
| Related models | Changing Category and redoing Product select_related | A real HIT is previously confirmed |
| Result isolation | Changing the list, model, JSON, select/prefetch | Re-reading from cache without SQL |
| Context | Nested scopes, gather, exception and cancel | Without global shared mutable state |
| Async ORM | aget/aexists | SQL is executed in the worker thread, a separate mark as a result |
| Tasks & retry | start, submit, repeat, SUCCESS, stop | In-process; non-durable distributed queue |
| DRF | to_drf_serializer, create, partial update, errors | The directory additionally restricts the queryset to the current session |
| Admin | compile_admin, forms, UI-schema | The real Admin entry is for staff only |
| Tracing & metrics | nova_span + local exporter + MetricsRegistry | There is no external OTLP; the timing value is indicated as an example |
| Redis backend | Serialization, TTL=0, generation change | Real service, separate namespace |
| Redis utilities | Competing lock, rate limit, Pub/Sub |Real Redis; limited wait |
| Memcached | Value independence, TTL=0, generation | Real service; no flush_all |
| FastAPI projection | to_fastapi_router + ASGI GET OpenAPI | Schema Preview; non-HTTP CRUD/runtime audit of the adapter |
| GraphQL projection | to_strawberry_type + execute_sync | Experimental; one fixed scalar read-only request |
| Migrations / router | SQL CreateIndexConcurrently and resetting replica state | DDL are not performed; replica is not configured |

The site demonstrates Nova subsystems using limited examples. Full regression analysis,
The competitive, multiprocess and load set of the main package is not duplicated here.
The number of green cards is not a metric of package coverage.