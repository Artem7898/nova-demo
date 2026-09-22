"""Language preference, request isolation and translated real UI/API responses."""

import json
import re

import pytest
from django.test import Client, override_settings

from catalog.models import DemoWorkspace, Product


def test_switch_language_preserves_location_session_and_catalog(visitor, csrf):
    workspace = visitor.session["workspace_id"]
    before = visitor.get("/api/products/").json()["results"]
    destination = "/catalog/?q=Nova&page=1"
    for language, heading in [("en", "Demo catalog"), ("ru", "Демо-каталог")]:
        response = visitor.post(
            "/i18n/setlang/", {"language": language, "next": destination}, **csrf
        )
        assert response.status_code == 302
        assert response["Location"] == destination
        assert visitor.cookies["django_language"].value == language
        page = visitor.get(destination)
        assert page["Content-Language"] == language
        assert f'<html lang="{language}"' in page.content.decode()
        assert heading in page.content.decode()
        assert visitor.session["workspace_id"] == workspace
        assert visitor.get("/api/products/").json()["results"] == before
    assert DemoWorkspace.objects.count() == 1
    assert Product.objects.count() == 8


def test_switch_requires_csrf_and_rejects_external_redirect(visitor, csrf):
    payload = {"language": "en", "next": "https://untrusted.example/"}
    assert visitor.post("/i18n/setlang/", payload).status_code == 403
    assert "django_language" not in visitor.cookies
    response = visitor.post("/i18n/setlang/", payload, **csrf)
    assert response.status_code == 302
    assert response["Location"] == "/"
    assert visitor.cookies["django_language"].value == "en"
    visitor.post("/i18n/setlang/", {"language": "zz", "next": "/"}, **csrf)
    assert visitor.cookies["django_language"].value == "en"


@pytest.mark.parametrize(
    "url,heading",
    [
        ("/", "Laboratory"),
        ("/catalog/", "Demo catalog"),
        ("/schemas/", "Schemas and contracts"),
        ("/integrations/", "Integrations"),
    ],
)
def test_english_pages_use_saved_preference(visitor, url, heading):
    visitor.cookies["django_language"] = "en"
    page = visitor.get(url, HTTP_ACCEPT_LANGUAGE="ru")
    html = page.content.decode()
    assert page.status_code == 200
    assert page["Content-Language"] == "en"
    assert heading in html
    assert 'class="language-switcher"' in html
    assert re.search(r'value="en"[^>]*aria-pressed="true"', html)
    assert re.search(r'value="ru"[^>]*aria-pressed="false"', html)


def test_product_detail_translates_interface_but_preserves_user_data(visitor):
    product = visitor.get("/api/products/").json()["results"][0]
    visitor.cookies["django_language"] = "en"
    page = visitor.get(f"/products/{product['id']}/")
    assert page.status_code == 200
    assert page["Content-Language"] == "en"
    assert product["name"] in page.content.decode()
    assert "language-switcher" in page.content.decode()


@pytest.mark.django_db
def test_browser_preference_and_default():
    for preference, expected in [("en-GB,en;q=0.9,ru;q=0.5", "en"), ("ru", "ru"), ("de", "ru")]:
        response = Client().get("/", HTTP_ACCEPT_LANGUAGE=preference)
        assert response["Content-Language"] == expected


def test_lazy_registry_is_localized_per_request(visitor):
    # Importing the registry or visiting in one language must not freeze its labels.
    for language, title, group in [
        ("en", "Model validation", "Basics"),
        ("ru", "Валидация модели", "Основы"),
        ("en", "Model validation", "Basics"),
    ]:
        visitor.cookies["django_language"] = language
        html = visitor.get("/").content.decode()
        match = re.search(r'<script id="scenario-data"[^>]*>(.*?)</script>', html, re.S)
        assert match is not None
        scenarios = json.loads(match.group(1))
        validation = next(item for item in scenarios if item["id"] == "validation")
        assert validation["title"] == title
        assert validation["group"] == group
        assert validation["group_id"] == "basics"


@pytest.mark.django_db(transaction=True)
def test_scenario_api_and_errors_follow_language():
    client = Client(enforce_csrf_checks=True)
    client.cookies["django_language"] = "en"
    client.get("/")
    token = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
    response = client.post(
        "/lab/api/run/validation/", data="invalid", content_type="application/json", **token
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid JSON."
    result = client.post(
        "/lab/api/run/cache/", data="{}", content_type="application/json", **token
    ).json()
    assert result["status"] == "passed", result
    assert "The repeated read executes no SQL" in json.dumps(result)
    with override_settings(NOVA_DEMO_REDIS_URL=""):
        response = client.post(
            "/lab/api/run/redis/", data="{}", content_type="application/json", **token
        )
    assert response.json()["status"] == "skipped"
    assert "Set NOVA_DEMO_REDIS_URL and start the service." in response.content.decode()


def test_javascript_catalog_is_language_specific_and_not_cached(visitor):
    visitor.cookies["django_language"] = "en"
    english = visitor.get("/jsi18n/")
    assert english.status_code == 200
    assert "Run scenario" in english.content.decode()
    assert "no-store" in english["Cache-Control"]
    visitor.cookies["django_language"] = "ru"
    russian = visitor.get("/jsi18n/")
    assert russian.status_code == 200
    assert "Run scenario" not in russian.content.decode()


def test_admin_login_follows_preference(visitor):
    visitor.cookies["django_language"] = "en"
    response = visitor.get("/admin/login/")
    assert response.status_code == 200
    assert "Log in" in response.content.decode()
    assert "Nova Demo · administration" in response.content.decode()
