import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.cloud_demo import configuration, create_demo_app, prepare_database
from app.infrastructure.database import get_db_path
from tests.conftest import PASSWORD, initialize, login
from tests.test_catalog import create, write
from tests.test_sales import intent

ORIGIN = "https://demo.example"
HOST = "pos-demo-api.onrender.com"
SECRET = "isolated-demo-test-secret-not-a-real-credential"


@pytest.fixture
def cloud_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("POS_CLOUD_DEMO", "1")
    monkeypatch.setenv("POS_PUBLIC_ORIGIN", ORIGIN)
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", HOST)
    monkeypatch.setenv("POS_DEMO_SETUP_TOKEN", SECRET)


def remote_client():
    return TestClient(create_demo_app(), base_url=f"https://{HOST}", headers={"Origin": ORIGIN})


def test_cloud_full_flow_and_restart_preserve_real_business_rules(cloud_env):
    with remote_client() as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert initialize(client, "x" * 43).status_code == 403
        assert initialize(client, SECRET).status_code == 201
        assert initialize(client, SECRET, "second").status_code == 409
        response = client.post("/api/auth/login", json={"username": "owner", "password": PASSWORD})
        assert response.status_code == 200
        assert all(flag in response.headers["set-cookie"] for flag in ["Secure", "HttpOnly", "SameSite=strict", "Path=/api"])
        csrf = response.json()["csrf_token"]
        assert write(client, csrf, "/api/employees", {"username": "worker", "password": PASSWORD}).status_code == 201
        assert write(client, csrf, "/api/categories", {"name": "Prueba"}).status_code == 201
        product = create(client, csrf, code=None, initial_stock=2, initial_reason="Prueba remota").json()
        body = intent(client, csrf, [{"product_id": product["id"], "quantity": 1}])
        sale = write(client, csrf, "/api/sales", body)
        assert sale.status_code == 201
        assert write(client, csrf, "/api/sales", body).json()["id"] == sale.json()["id"]
        assert client.get(f"/api/products/{product['id']}").json()["stock_quantity"] == 1
        assert write(client, csrf, "/api/sales/quote", {"items": [{"product_id": product["id"], "quantity": 2}]}).status_code == 409
        report = client.get("/api/reports/summary", params={"period": "today"})
        assert report.status_code == 200
        assert report.json()["current"]["sales"] == "1"
        assert write(client, csrf, f"/api/sales/{sale.json()['id']}/void", {"reason": "Prueba"}).status_code == 200
        assert client.get(f"/api/products/{product['id']}").json()["stock_quantity"] == 2
        assert write(client, csrf, "/api/auth/logout", {}).status_code == 204
        csrf = login(client, "worker")
        assert client.get("/api/employees").status_code == 403
        assert client.get("/api/reports/summary", params={"period": "today"}).status_code == 403
        assert create(client, csrf, code="employee-denied").status_code == 403
    with remote_client() as client:
        assert client.get("/api/auth/setup").json() == {"initialized": True}
        login(client)
        assert client.get(f"/api/products/{product['id']}").json()["stock_quantity"] == 2
        assert client.get(f"/api/sales/{sale.json()['id']}").json()["status"] == "VOIDED"


def test_remote_origin_host_and_csrf_are_enforced(cloud_env):
    with remote_client() as client:
        assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400
        assert client.get("/api/auth/setup", headers={"Origin": "https://evil.example"}).status_code == 403
        client.headers.pop("Origin")
        assert initialize(client, SECRET).status_code == 403
        client.headers["Origin"] = ORIGIN
        assert initialize(client, SECRET).status_code == 201
        login(client)
        assert client.post("/api/employees", json={"username": "worker", "password": PASSWORD}).status_code == 403


def test_remote_auth_attempts_are_bounded(cloud_env):
    with remote_client() as client:
        for _ in range(20):
            assert client.post("/api/auth/login", json={}).status_code == 422
        response = client.post("/api/auth/login", json={})
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"


@pytest.mark.parametrize("key,value", [
    ("POS_CLOUD_DEMO", "0"), ("POS_PUBLIC_ORIGIN", "http://demo.example"),
    ("POS_PUBLIC_ORIGIN", "https://demo.example/path"),
    ("POS_PUBLIC_ORIGIN", "https://demo.example?query=value"),
    ("POS_PUBLIC_ORIGIN", "https://*.example"),
    ("RENDER_EXTERNAL_HOSTNAME", "evil.example"),
    ("POS_DEMO_SETUP_TOKEN", "short"), ("LOCALAPPDATA", ""),
])
def test_cloud_configuration_fails_closed_before_creating_data(cloud_env, monkeypatch, key, value):
    path = get_db_path()
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        configuration()
    assert not path.exists()


def test_existing_incompatible_database_is_never_automatically_migrated(cloud_env):
    path = get_db_path()
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE marker(value TEXT)")
        db.execute("INSERT INTO marker VALUES('preserve')")
    with pytest.raises(RuntimeError):
        prepare_database(SECRET)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT value FROM marker").fetchall() == [("preserve",)]
        assert db.execute("SELECT name FROM sqlite_master WHERE name='users'").fetchall() == []
