"""Small demo uploads remain private to their visitor workspace and staff."""

import mimetypes
import uuid

from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpRequest
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .models import Product, ProductPhoto


@require_safe
@never_cache
def uploaded_image(request: HttpRequest, path: str) -> FileResponse:
    products = Product.objects.filter(preview=path)
    photos = ProductPhoto.objects.filter(image=path)
    if not getattr(request.user, "is_staff", False):
        try:
            workspace = uuid.UUID(str(request.session.get("workspace_id", "")))
        except ValueError:
            raise Http404 from None
        products = products.filter(category__workspace_id=workspace)
        photos = photos.filter(product__category__workspace_id=workspace)
    product = products.first()
    photo = None if product else photos.first()
    if product:
        field = product.preview
    elif photo:
        field = photo.image
    else:
        raise Http404
    content_type = mimetypes.guess_type(field.name)[0]
    # Do not serve active document types, including SVG, from uploaded media.
    if content_type not in {"image/png", "image/jpeg", "image/gif", "image/webp", "image/avif"}:
        raise Http404
    try:
        file = field.storage.open(field.name, "rb")
    except (OSError, SuspiciousFileOperation):
        raise Http404 from None
    response = FileResponse(file, content_type=content_type)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
