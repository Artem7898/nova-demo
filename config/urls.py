from django.contrib import admin
from django.urls import include, path
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.i18n import JavaScriptCatalog
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from catalog import front
from catalog.media import uploaded_image
from config.health import readiness

admin.site.site_header = gettext_lazy("Nova Demo · управление")
admin.site.site_title = "Nova Demo"
admin.site.site_url = "/"
urlpatterns = [
    path("healthz/", readiness, name="readiness"),
    path("media/<path:path>", uploaded_image, name="uploaded-image"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("jsi18n/", never_cache(JavaScriptCatalog.as_view()), name="javascript-catalog"),
    path("", front.home, name="home"),
    path("catalog/", front.catalog, name="catalog"),
    path("products/<int:pk>/", front.product_detail, name="product-detail"),
    path("schemas/", front.schemas, name="schemas"),
    path("integrations/", front.integrations, name="integrations"),
    path("lab/api/health/", front.health, name="health"),
    path("lab/api/run/<slug:scenario_id>/", front.run_lab, name="run-lab"),
    path("lab/api/schema/<slug:model>/", front.schema_data, name="schema-data"),
    path("cache/stats/", front.cache_stats, name="cache-stats"),
    path("admin/", admin.site.urls),
    path("api/", include("catalog.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
]
