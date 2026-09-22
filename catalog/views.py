from decimal import Decimal, InvalidOperation

from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext
from django.views.decorators.csrf import csrf_protect
from nova.core.exceptions import NovaValidationError
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Category, Product, Report
from .serializers import CategorySerializer, ProductSerializer, ReportSerializer
from .tasks import execute_report
from .workspaces import get_workspace


class WorkspaceMixin(viewsets.GenericViewSet):
    def workspace(self):
        if not hasattr(self, "_workspace"):
            self._workspace = get_workspace(self.request)
        return self._workspace

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if not getattr(self, "swagger_fake_view", False):
            context["workspace"] = self.workspace()
        return context

    def handle_exception(self, exc):
        if isinstance(exc, (NovaValidationError, DjangoValidationError)):
            exc = serializers.ValidationError({"detail": str(exc)})
        elif isinstance(exc, IntegrityError):
            exc = serializers.ValidationError(
                {"detail": gettext("Операция нарушает ограничение базы данных.")}
            )
        return super().handle_exception(exc)


@method_decorator(csrf_protect, name="dispatch")
class CategoryViewSet(WorkspaceMixin, viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.none()

    def get_queryset(self):
        return (
            Category.objects.none()
            if getattr(self, "swagger_fake_view", False)
            else Category.objects.filter(workspace=self.workspace()).order_by("id")
        )

    def perform_create(self, serializer):
        if self.get_queryset().count() >= 12:
            raise serializers.ValidationError(gettext("Лимит песочницы: 12 категорий."))
        serializer.save(workspace=self.workspace())

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        if category.products.exists():
            return Response({"detail": gettext("Сначала удалите товары категории.")}, status=409)
        return super().destroy(request, *args, **kwargs)


@method_decorator(csrf_protect, name="dispatch")
class ProductViewSet(WorkspaceMixin, viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Product.objects.none()
        qs = (
            Product.objects.filter(category__workspace=self.workspace())
            .select_related("category")
            .order_by("id")
        )
        if value := self.request.query_params.get("min_price"):
            try:
                price = Decimal(value)
                if not price.is_finite():
                    raise InvalidOperation
            except InvalidOperation as exc:
                raise serializers.ValidationError(
                    {"min_price": gettext("Укажите конечное число.")}
                ) from exc
            qs = qs.filter(price__gte=price)
        return qs

    def perform_create(self, serializer):
        if Product.objects.filter(category__workspace=self.workspace()).count() >= 50:
            raise serializers.ValidationError(gettext("Лимит песочницы: 50 товаров."))
        with transaction.atomic():
            serializer.save()

    def perform_update(self, serializer):
        with transaction.atomic():
            serializer.save()


@method_decorator(csrf_protect, name="dispatch")
class ReportViewSet(WorkspaceMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ReportSerializer
    queryset = Report.objects.none()

    def get_queryset(self):
        return (
            Report.objects.none()
            if getattr(self, "swagger_fake_view", False)
            else Report.objects.filter(category__workspace=self.workspace()).order_by("-id")
        )

    @action(detail=False, methods=["post"])
    def run(self, request):
        category_id = serializers.IntegerField(min_value=1).run_validation(
            request.data.get("category")
        )
        category = Category.objects.filter(workspace=self.workspace(), pk=category_id).first()
        if category is None:
            raise serializers.ValidationError(
                {"category": gettext("Выберите категорию своей песочницы.")}
            )
        if self.get_queryset().count() >= 30:
            raise serializers.ValidationError(gettext("Лимит песочницы: 30 отчётов."))
        prices = list(Product.objects.filter(category=category).values_list("price", flat=True))
        result = async_to_sync(execute_report)(prices)
        report = Report.objects.create(
            category=category,
            status=Report.Status.DONE,
            result=result["result"],
            task_id=result["id"],
            finished_at=timezone.now(),
        )
        return Response(ReportSerializer(report).data, status=201)
