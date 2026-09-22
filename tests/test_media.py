from io import BytesIO

import pytest
from django.core.files.base import ContentFile
from django.test import Client
from PIL import Image

from catalog.models import Product, ProductPhoto


@pytest.mark.parametrize("gallery", [False, True])
def test_uploaded_images_respect_workspace_and_staff(visitor, admin_client, gallery):
    product = Product.objects.filter(category__workspace_id=visitor.session["workspace_id"]).first()
    output = BytesIO()
    Image.new("RGB", (2, 2), "blue").save(output, format="PNG")
    if gallery:
        photo = ProductPhoto(product=product, caption="Deployment test")
        photo.image.save("test.png", ContentFile(output.getvalue()), save=True)
        field = photo.image
    else:
        product.preview.save("test.png", ContentFile(output.getvalue()), save=True)
        field = product.preview
    for allowed in (visitor, admin_client):
        response = allowed.get(field.url)
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        assert "no-store" in response["Cache-Control"]
        assert response["X-Content-Type-Options"] == "nosniff"
        # Django's test client closes a consumed streaming response itself.
        assert b"".join(response.streaming_content) == output.getvalue()
    other = Client()
    assert other.get(field.url).status_code == 404
    assert other.get("/").status_code == 200
    assert other.get(field.url).status_code == 404
    field.storage.delete(field.name)
    assert visitor.get(field.url).status_code == 404


def test_media_rejects_active_documents_and_unregistered_files(visitor):
    product = Product.objects.filter(category__workspace_id=visitor.session["workspace_id"]).first()
    # Bypass upload form validation to exercise the serving boundary itself.
    product.preview.save("unsafe.svg", ContentFile(b"<svg/>"), save=True)
    assert visitor.get(product.preview.url).status_code == 404
    assert visitor.get("/media/unknown.png").status_code == 404
    assert visitor.get("/media/../../config/settings.py").status_code == 404
