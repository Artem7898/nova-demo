import pytest
from django.test import Client, override_settings

from catalog.models import Category, Product


@pytest.mark.parametrize(
    "url",
    [
        "/",
        "/catalog/",
        "/schemas/",
        "/integrations/",
        "/api/docs/",
        "/api/schema/",
        "/cache/stats/",
    ],
)
def test_pages_render(visitor, url):
    response = visitor.get(url)
    assert response.status_code == 200


@pytest.mark.parametrize("model", ["product", "category", "tag", "report"])
def test_schema_inspection(visitor, model):
    result = visitor.get(f"/lab/api/schema/{model}/")
    assert result.status_code == 200
    assert result.json()["schema"]["properties"]
    assert result.json()["fields"]


def test_health_is_honest(visitor):
    with override_settings(NOVA_DEMO_REDIS_URL="", NOVA_DEMO_MEMCACHED_SERVER=""):
        services = visitor.get("/lab/api/health/").json()["services"]
    assert services["database"]["status"] == "ready"
    assert services["redis"]["status"] == services["memcached"]["status"] == "not_configured"


def test_sessions_do_not_expose_other_visitors(visitor, csrf):
    other = Client()
    other.get("/")
    mine = visitor.get("/api/products/").json()["results"]
    theirs = other.get("/api/products/").json()["results"]
    assert len(mine) == len(theirs) == 8
    assert not {p["id"] for p in mine} & {p["id"] for p in theirs}
    foreign = theirs[0]
    assert visitor.get(f"/products/{foreign['id']}/").status_code == 404
    assert visitor.get(f"/api/products/{foreign['id']}/").status_code == 404
    assert (
        visitor.patch(
            f"/api/products/{foreign['id']}/",
            {"name": "hijack"},
            content_type="application/json",
            **csrf,
        ).status_code
        == 404
    )
    assert visitor.delete(f"/api/products/{foreign['id']}/", **csrf).status_code == 404
    response = visitor.post(
        "/api/products/",
        {"name": "Other category", "price": "20", "category": foreign["category"]},
        content_type="application/json",
        **csrf,
    )
    assert response.status_code == 400


def test_product_create_patch_validation_and_delete(visitor, csrf):
    category = visitor.get("/api/categories/").json()["results"][0]["id"]
    data = {"name": "Demo test", "price": "29.99", "category": category, "metadata": {"x": [1]}}
    assert visitor.post("/api/products/", data, content_type="application/json").status_code == 403
    response = visitor.post("/api/products/", data, content_type="application/json", **csrf)
    assert response.status_code == 201, response.content
    pk = response.json()["id"]
    response = visitor.patch(
        f"/api/products/{pk}/", {"price": "-1"}, content_type="application/json", **csrf
    )
    assert response.status_code == 400, response.content
    assert str(Product.objects.get(pk=pk).price) == "29.99"
    response = visitor.patch(
        f"/api/products/{pk}/", {"price": "31.00"}, content_type="application/json", **csrf
    )
    assert response.status_code == 200, response.content
    assert response.json()["price"] == "31.00"
    assert visitor.delete(f"/api/products/{pk}/", **csrf).status_code == 204
    assert not Product.objects.filter(pk=pk).exists()


def test_category_creation_and_protected_delete(visitor, csrf):
    response = visitor.post(
        "/api/categories/", {"name": "New category"}, content_type="application/json", **csrf
    )
    assert response.status_code == 201, response.content
    obj = Category.objects.get(pk=response.json()["id"])
    assert str(obj.workspace_id) == visitor.session["workspace_id"]
    used = visitor.get("/api/products/").json()["results"][0]["category"]
    assert visitor.delete(f"/api/categories/{used}/", **csrf).status_code == 409
    assert visitor.delete(f"/api/categories/{obj.pk}/", **csrf).status_code == 204


@pytest.mark.parametrize("price", ["nan", "Infinity", "abc"])
def test_bad_price_filter_returns_400(visitor, price):
    assert visitor.get("/api/products/", {"min_price": price}).status_code == 400


@pytest.mark.django_db(transaction=True)
def test_report_completes_once_and_validates_category():
    c = Client(enforce_csrf_checks=True)
    c.get("/")
    token = {"HTTP_X_CSRFTOKEN": c.cookies["csrftoken"].value}
    category = c.get("/api/categories/").json()["results"][0]["id"]
    for bad in ("abc", None, -1):
        assert (
            c.post(
                "/api/reports/run/", {"category": bad}, content_type="application/json", **token
            ).status_code
            == 400
        )
    response = c.post(
        "/api/reports/run/", {"category": category}, content_type="application/json", **token
    )
    assert response.status_code == 201, response.content
    assert response.json()["status"] == "done"
    assert response.json()["result"]["attempts"] == 1


def test_admin_requires_login(visitor):
    assert visitor.get("/admin/").status_code == 302
    assert visitor.get("/admin/login/").status_code == 200
