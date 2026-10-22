"""Preservar F3 y recuperar migración interrumpida sin tocar instalaciones reales."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from alembic import command
from app.infrastructure.schema import SchemaCompatibilityError
from app.main import create_app
from tests.conftest import ORIGIN

pytest_plugins = ("tests.test_catalog_migrations",)


@pytest.fixture
def f3_database(old_database):
    config, scripts, path, cookie = old_database
    command.upgrade(config, "0003_catalog_inventory")
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("INSERT INTO categories VALUES(8,'Bebidas','bebidas',1)")
        db.execute("INSERT INTO products VALUES(13,'0001','Agua',8,12550,10000,3,1,1,'2026-10-22','2026-10-22')")
        db.execute("INSERT INTO stock_movements VALUES(9,13,'INITIAL',3,0,3,'PRODUCT',13,7,'Carga inicial',NULL,'2026-10-22')")
    return config, scripts, path, cookie


def test_upgrade_preserves_all_f3_rows_and_session(f3_database):
    config, _, path, cookie = f3_database
    with sqlite3.connect(path) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='alembic_version'")]
        before = {table: db.execute("SELECT * FROM " + table).fetchall() for table in tables}
    with pytest.raises(SchemaCompatibilityError), TestClient(create_app(path)):
        pytest.fail("F4 debe rechazar F3 antes de migrar")
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with sqlite3.connect(path) as db:
        for table, rows in before.items():
            assert db.execute("SELECT * FROM " + table).fetchall() == rows
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with TestClient(create_app(path), base_url="http://127.0.0.1", headers={"origin": ORIGIN, "cookie": f"pos_session={cookie}"}) as client:
        assert client.get("/api/auth/me").status_code == 200
        assert client.get("/api/products/13").json()["stock_quantity"] == 3
        assert client.get("/api/sales").json() == {"items": [], "total": 0}


def test_interrupted_f4_ddl_rolls_back_and_retries(f3_database):
    config, scripts, path, _ = f3_database
    with sqlite3.connect(path) as db:
        before = list(db.iterdump())
    file = scripts / "versions/0004_checkout_history.py"
    original = file.read_text()
    file.write_text(original.replace("        op.execute(statement)", '        if statement.startswith("CREATE TABLE payments"):\n            raise RuntimeError("interrupción F4")\n        op.execute(statement)'))
    with pytest.raises(RuntimeError, match="interrupción F4"):
        command.upgrade(config, "head")
    with sqlite3.connect(path) as db:
        assert list(db.iterdump()) == before
    file.write_text(original)
    command.upgrade(config, "head")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0006_local_operations",)
        assert db.execute("SELECT stock_quantity FROM products WHERE id=13").fetchone() == (3,)
