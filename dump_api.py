import inspect
from nova.cache.queryset_cache import QuerySetCache, get_default_cache
from nova.cache.invalidation import connect_invalidation
from nova.tasks.engine import get_engine
from nova.validation.unified import validate_model_instance
from nova.validation.pydantic_bridge import generate_pydantic_schema, pydantic_to_model, model_to_pydantic
from nova.validation.schema_registry import SchemaRegistry
from nova.db.splitter import chunked_migration
from nova.db.zero_downtime import CreateIndexConcurrently, AddFieldConcurrently
from nova.tasks.decorators import nova_task

for title, obj in (("QuerySetCache", QuerySetCache), ("get_default_cache()", get_default_cache()), ("engine", get_engine())):
    print(f"=== {title} ===")
    for m in [m for m in dir(obj) if not m.startswith("_")]:
        try: print(" ", m, inspect.signature(getattr(obj, m)))
        except Exception: print(" ", m)

for f in (connect_invalidation, validate_model_instance, generate_pydantic_schema,
          pydantic_to_model, model_to_pydantic, chunked_migration, nova_task):
    print(f.__name__, inspect.signature(f))

print("SchemaRegistry:", [m for m in dir(SchemaRegistry) if not m.startswith("_")])
print("CreateIndexConcurrently:", inspect.signature(CreateIndexConcurrently.__init__))
print("AddFieldConcurrently:", inspect.signature(AddFieldConcurrently.__init__))
