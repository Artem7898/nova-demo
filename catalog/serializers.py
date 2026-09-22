import uuid

from nova.ecosystem.drf import to_drf_serializer
from rest_framework import serializers

from .models import Category, Product, Report


class CategorySerializer(to_drf_serializer(Category)):
    def validate(self, attrs):
        if self.instance is None:
            attrs["slug"] = f"c-{uuid.uuid4().hex}"
        return super().validate(attrs)

    class Meta:
        model = Category
        fields = ("id", "name", "slug")
        read_only_fields = ("id", "slug")


class ProductSerializer(to_drf_serializer(Product)):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "price",
            "is_active",
            "category",
            "category_name",
            "metadata",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        workspace = self.context.get("workspace")
        self.fields["category"].queryset = (
            Category.objects.filter(workspace=workspace) if workspace else Category.objects.none()
        )


class ReportSerializer(serializers.ModelSerializer):
    # DRF reads Meta as per-model configuration.
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = Report
        fields = (
            "id",
            "category",
            "status",
            "result",
            "error",
            "task_id",
            "created_at",
            "finished_at",
        )
