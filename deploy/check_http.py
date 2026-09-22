"""Exercise the production HTTP stack behind a simulated Railway HTTPS proxy."""

import http.client
import json
import re
import sys
import time
from http.cookies import SimpleCookie
from urllib.parse import urlencode, urlsplit


def check(base_url: str, *, require_services: bool = False) -> None:
    target = urlsplit(base_url)
    cookies: dict[str, str] = {}

    def request(
        path, method="GET", data=None, *, secure=True, host="demo.example", json_body=False
    ):
        connection = http.client.HTTPConnection(target.hostname, target.port, timeout=10)
        headers = {"Host": host, "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}
        if secure:
            headers["X-Forwarded-Proto"] = "https"
        if data is not None:
            headers["Content-Type"] = (
                "application/json" if json_body else "application/x-www-form-urlencoded"
            )
            headers["X-CSRFToken"] = cookies["csrftoken"]
            headers["Origin"] = f"https://{host}"
        try:
            body = (
                (json.dumps(data) if json_body else urlencode(data)) if data is not None else None
            )
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            body = response.read()
            for name, value in response.getheaders():
                if name.lower() == "set-cookie":
                    parsed = SimpleCookie(value)
                    for key, morsel in parsed.items():
                        assert morsel["secure"], f"Insecure {key} cookie"
                        cookies[key] = morsel.value
            return response.status, dict(response.getheaders()), body
        finally:
            connection.close()

    deadline = time.monotonic() + 60
    while True:
        try:
            status, headers, body = request(
                "/healthz/", secure=False, host="healthcheck.railway.app"
            )
            assert status == 200 and json.loads(body) == {"status": "ok"}
            assert not cookies, "Readiness created a visitor session"
            break
        except (OSError, AssertionError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.25)
    status, headers, _ = request("/", secure=False)
    assert status == 301 and headers["Location"] == "https://demo.example/"
    status, _, html = request("/")
    assert status == 200 and "sessionid" in cookies and "csrftoken" in cookies
    asset = re.search(rb'"(/static/demo/app\.[^"/]+\.css)"', html)
    assert asset, "Missing hashed CSS reference"
    assert request(asset[1].decode())[0] == 200
    original_session = cookies["sessionid"]
    for language in ("en", "ru"):
        assert (
            request("/i18n/setlang/", "POST", {"language": language, "next": "/catalog/"})[0] == 302
        )
        status, headers, body = request("/catalog/")
        assert status == 200 and headers["Content-Language"] == language
        assert f'<html lang="{language}"'.encode() in body
        assert cookies["sessionid"] == original_session
    status, _, body = request("/api/products/")
    assert status == 200 and json.loads(body)["count"] == 8
    assert request("/", host="untrusted.example")[0] == 400
    print("OK readiness, HTTPS, static CSS, secure cookies, RU/EN, catalog and host validation")
    if require_services:
        status, _, body = request("/lab/api/health/")
        health = json.loads(body)
        assert status == 200
        assert health["services"]["database"]["label"] == "postgresql"
        assert all(item["status"] == "ready" for item in health["services"].values())
        catalog = re.search(
            rb'<script id="scenario-data" type="application/json">(.*?)</script>', html, re.S
        )
        assert catalog, "Missing scenario catalog"
        scenarios = json.loads(catalog[1])
        assert len(scenarios) == 19
        for scenario in scenarios:
            status, _, body = request(
                f"/lab/api/run/{scenario['id']}/", "POST", scenario["payload"], json_body=True
            )
            result = json.loads(body)
            assert status == 200 and result["status"] == "passed", (scenario, result)
        print(f"OK {len(scenarios)}/{len(scenarios)} scenarios via production HTTP")


if __name__ == "__main__":
    check(sys.argv[1], require_services="--require-services" in sys.argv[2:])
