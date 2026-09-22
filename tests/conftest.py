import pytest
from django.core.cache import cache
from django.test import Client


@pytest.fixture(autouse=True)
def reset_throttles():
    cache.clear()


@pytest.fixture
def visitor(db):
    client = Client(enforce_csrf_checks=True)
    assert client.get("/").status_code == 200
    return client


@pytest.fixture
def csrf(visitor):
    return {"HTTP_X_CSRFTOKEN": visitor.cookies["csrftoken"].value}
