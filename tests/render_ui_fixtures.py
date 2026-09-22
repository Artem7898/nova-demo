"""Render real templates in an isolated temporary database for DOM tests."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")

import django
from django.conf import settings
from django.core.management import call_command
from django.core.serializers.json import DjangoJSONEncoder
from django.test import Client
from django.utils import translation

with tempfile.TemporaryDirectory(prefix="nova-ui-") as temporary:
    settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(Path(temporary) / "ui.sqlite3"),
        }
    }
    settings.ALLOWED_HOSTS = ["testserver"]
    django.setup()
    call_command("migrate", verbosity=0)
    from catalog.lab.runner import run_scenario

    fixtures = {}
    for language in ("ru", "en"):
        client = Client()
        client.cookies["django_language"] = language
        pages = {
            url: client.get(url).content.decode()
            for url in ("/", "/catalog/", "/schemas/", "/integrations/")
        }
        api = {
            url: client.get(url).json()
            for url in ("/lab/api/health/", "/lab/api/schema/product/", "/lab/api/schema/category/")
        }
        with translation.override(language):
            for scenario in ("validation", "cache"):
                api[f"/lab/api/run/{scenario}/"] = run_scenario(scenario)
            fixtures[language] = json.loads(
                json.dumps(
                    {
                        "pages": pages,
                        "api": api,
                        "catalog": client.get("/jsi18n/").content.decode(),
                    },
                    cls=DjangoJSONEncoder,
                )
            )
    print(json.dumps(fixtures))
