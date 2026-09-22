from django.contrib import admin
from django.utils.translation import gettext_lazy
from nova.admin.api import compile_admin

from .forms import ProductAdminForm
from .models import Category, Product, ProductPhoto, Report, Tag


@admin.register(Category)
class CategoryAdmin(compile_admin(Category)):
    list_display = ("name", "slug", "workspace")
    search_fields = ("name", "slug")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


class ProductPhotoInline(admin.TabularInline):
    model = ProductPhoto
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("name", "category", "price", "is_active", "created_at")
    list_filter = ("is_active", "category")
    search_fields = ("name",)
    autocomplete_fields = ("category",)
    filter_horizontal = ("tags",)
    readonly_fields = ("created_at",)
    inlines = [ProductPhotoInline]
    actions = ["activate", "deactivate"]

    @admin.action(description=gettext_lazy("Активировать с валидацией и инвалидацией"))
    def activate(self, request, queryset):
        for product in queryset:
            product.is_active = True
            product.save(update_fields=["is_active"])

    @admin.action(description=gettext_lazy("Деактивировать с валидацией и инвалидацией"))
    def deactivate(self, request, queryset):
        for product in queryset:
            product.is_active = False
            product.save(update_fields=["is_active"])


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "status", "created_at")
    readonly_fields = ("result", "task_id", "error", "finished_at")
