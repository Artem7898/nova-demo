from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ProductViewSet, ReportViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("products", ProductViewSet)
router.register("reports", ReportViewSet)

urlpatterns = router.urls
