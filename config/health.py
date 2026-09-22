"""Readiness without creating visitor workspaces or probing optional services."""

from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe


@require_safe
@never_cache
def readiness(request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
