"""Visitors have separate demo data; existing catalog rows remain private."""

from decimal import Decimal

from django.db import transaction

from .models import Category, DemoWorkspace, Product, Tag

SAMPLES = [
    ("Studio Headphones", "Аудио", "129.00", "headphones"),
    ("Mechanical Keyboard", "Рабочее место", "159.00", "keyboard"),
    ("Portable Speaker", "Аудио", "89.00", "speaker"),
    ("Focus Desk Lamp", "Рабочее место", "64.00", "lamp"),
    ("Studio Microphone", "Аудио", "119.00", "microphone"),
    ("Everyday Backpack", "Аксессуары", "79.00", "bag"),
    ("Wireless Mouse", "Рабочее место", "49.00", "mouse"),
    ("USB-C Hub", "Аксессуары", "59.00", "hub"),
]


def seed_workspace(workspace):
    categories = {}
    for index, name in enumerate(dict.fromkeys(x[1] for x in SAMPLES)):
        categories[name] = Category.objects.create(
            name=name, slug=f"d-{workspace.pk.hex}-{index}", workspace=workspace
        )
    tag, _ = Tag.objects.get_or_create(name="Demo collection")
    for name, category, price, illustration in SAMPLES:
        product = Product.objects.create(
            name=name,
            category=categories[category],
            price=Decimal(price),
            metadata={
                "illustration": illustration,
                "specs": {"edition": "2026", "warranty": "24 months"},
            },
        )
        product.tags.add(tag)
    return workspace


def get_workspace(request):
    workspace_id = request.session.get("workspace_id")
    if workspace_id:
        workspace = DemoWorkspace.objects.filter(pk=workspace_id).first()
        if workspace:
            return workspace
    with transaction.atomic():
        workspace = seed_workspace(DemoWorkspace.objects.create())
    request.session["workspace_id"] = str(workspace.pk)
    return workspace
