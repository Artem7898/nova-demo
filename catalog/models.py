import uuid
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy
from nova.typing.managers import NovaManager
from nova.typing.models import NovaConfig, NovaModel

# Django uses a separate Meta configuration class per model, not a shared value.
from .schemas import CategoryContract, ProductContract, ProductReadContract


class DemoWorkspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Category(NovaModel):
    _nova_config = NovaConfig(pydantic_schema=CategoryContract)
    workspace = models.ForeignKey(DemoWorkspace, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(gettext_lazy("Название"), max_length=100)
    slug = models.SlugField(unique=True)

    objects = NovaManager()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = gettext_lazy("Категория")
        verbose_name_plural = gettext_lazy("Категории")

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        if self.name and not any(ch.isalpha() for ch in self.name):
            raise ValidationError(
                {"name": gettext_lazy("Название не может состоять только из цифр/символов")}
            )


class Tag(NovaModel):
    name = models.CharField(gettext_lazy("Тег"), max_length=50, unique=True)
    objects = NovaManager()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = gettext_lazy("Тег")
        verbose_name_plural = gettext_lazy("Теги")

    def __str__(self) -> str:
        return self.name


class Product(NovaModel):
    _nova_config = NovaConfig(pydantic_schema=ProductContract, cache_enabled=True)
    metadata = models.JSONField(default=dict, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name=gettext_lazy("Категория"),
    )
    name = models.CharField(gettext_lazy("Название"), max_length=200)
    price = models.DecimalField(gettext_lazy("Цена"), max_digits=10, decimal_places=2)
    is_active = models.BooleanField(gettext_lazy("Активен"), default=True)
    preview = models.ImageField(
        gettext_lazy("Превью"), upload_to="products/%Y/%m/", blank=True, null=True
    )
    tags = models.ManyToManyField(Tag, blank=True, verbose_name=gettext_lazy("Теги"))
    created_at = models.DateTimeField(gettext_lazy("Создан"), auto_now_add=True)

    objects = NovaManager()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = gettext_lazy("Товар")
        verbose_name_plural = gettext_lazy("Товары")
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name="product_price_gt_0"),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        if self.price is not None:
            try:
                price = Decimal(str(self.price))
            except (InvalidOperation, TypeError) as exc:
                raise ValidationError(
                    {"price": gettext_lazy("Некорректное значение цены")}
                ) from exc
            if not price.is_finite() or not Decimal("0") < price <= Decimal("1000000"):
                raise ValidationError(
                    {"price": gettext_lazy("Цена должна быть больше 0 и не превышать 1 000 000")}
                )
            self.price = price


class ProductPhoto(NovaModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="photos", verbose_name=gettext_lazy("Товар")
    )
    image = models.ImageField(gettext_lazy("Фото"), upload_to="products/gallery/")
    caption = models.CharField(gettext_lazy("Подпись"), max_length=200, blank=True)
    objects = NovaManager()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = gettext_lazy("Фото товара")
        verbose_name_plural = gettext_lazy("Фото товаров")

    def __str__(self) -> str:
        return gettext_lazy("Фото #{pk} → {product}").format(pk=self.pk, product=self.product)


class Report(NovaModel):
    class Status(models.TextChoices):
        PENDING = "pending", gettext_lazy("В очереди")
        RUNNING = "running", gettext_lazy("Выполняется")
        DONE = "done", gettext_lazy("Готов")
        FAILED = "failed", gettext_lazy("Ошибка")

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="reports")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    task_id = models.CharField(gettext_lazy("ID задачи движка"), max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    objects = NovaManager()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        verbose_name = gettext_lazy("Отчёт")
        verbose_name_plural = gettext_lazy("Отчёты")


class ProductReadPlan(NovaModel):
    """Abstract projection for planning; never registers a second SQL-table model."""

    _nova_config = NovaConfig(pydantic_schema=ProductReadContract)
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="+")
    tags = models.ManyToManyField(Tag, related_name="+")

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        abstract = True
