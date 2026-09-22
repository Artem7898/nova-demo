from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"

    def ready(self):
        from nova.cache.invalidation import connect_invalidation

        from . import telemetry  # noqa: F401
        from .models import Product

        connect_invalidation(Product)
