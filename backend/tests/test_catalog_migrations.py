"""Actualizar datos F2 y fallar a mitad de F3 sin pérdida ni reparación destructiva."""

import shutil
import sqlite3
import time
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from app.application.identity import digest
from app.infrastructure.passwords import ArgonPasswords
from app.infrastructure.schema import SchemaCompatibilityError
from app.main import create_app
from tests.conftest import ORIGIN, PASSWORD


@pytest.fixture
def old_database(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    backend = Path(__file__).resolve().parents[1]
    scripts = tmp_path / "migrations"
    shutil.copytree(backend / "alembic", scripts)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(scripts))
    command.upgrade(config, "0002_identity")
    path = tmp_path / "GestionInteligentePOS/data/pos.db"
    encoded = ArgonPasswords().hash(PASSWORD)
    cookie = "synthetic-session-for-migration-test"
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO users(id,username,password_hash,role,is_active,created_at) VALUES(7,'historical',?,'ADMIN',1,'2026-10-22T00:00:00+00:00')",
            (encoded,),
        )
        db.execute("INSERT INTO bootstrap VALUES(1,NULL,0,1)")
        db.execute("INSERT INTO sessions VALUES(?,7,?)", (digest(cookie), int(time.time()) + 3600))
        db.execute(
            "INSERT INTO audit_log VALUES(23,7,'ADMIN_INITIALIZED','users',7,'{}','2026-10-22T00:00:00+00:00')"
        )
    return config, scripts, path, cookie


def test_upgrade_preserves_identity_sessions_and_audit(old_database):
    config, _, path, cookie = old_database
    with sqlite3.connect(path) as db:
        originals = {
            table: db.execute("SELECT * FROM " + table).fetchall()
            for table in ("users", "sessions", "bootstrap", "audit_log")
        }
    with pytest.raises(SchemaCompatibilityError), TestClient(create_app(path)):
        pytest.fail("F3 no debe abrir un esquema F2 sin migrar")
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with sqlite3.connect(path) as db:
        for table, rows in originals.items():
            assert db.execute("SELECT * FROM " + table).fetchall() == rows
        assert db.execute("SELECT * FROM audit_events").fetchall() == originals["audit_log"]
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with TestClient(
        create_app(path),
        base_url="http://127.0.0.1",
        headers={"origin": ORIGIN, "cookie": f"pos_session={cookie}"},
    ) as client:
        session = client.get("/api/auth/me")
        assert session.status_code == 200 and session.json()["user"]["username"] == "historical"
        response = client.post(
            "/api/categories",
            json={"name": "Nueva"},
            headers={"x-csrf-token": session.json()["csrf_token"]},
        )
        assert response.status_code == 201
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM audit_events").fetchone() == (2,)
        assert db.execute("SELECT COUNT(*) FROM audit_log").fetchone() == (1,)


def test_f3_failure_preserves_f2_and_can_retry(old_database):
    config, scripts, path, _ = old_database
    with sqlite3.connect(path) as db:
        before = list(db.iterdump())
    file = scripts / "versions/0003_catalog_inventory.py"
    original = file.read_text()
    file.write_text(
        original.replace(
            "        op.execute(statement)",
            '        if statement.startswith("CREATE TABLE products"):\n            raise RuntimeError("interrupción F3")\n        op.execute(statement)',
        )
    )
    with pytest.raises(RuntimeError, match="interrupción F3"):
        command.upgrade(config, "head")
    with sqlite3.connect(path) as db:
        assert list(db.iterdump()) == before
    file.write_text(original)
    command.upgrade(config, "head")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0006_local_operations",
        )
        assert db.execute("SELECT COUNT(*) FROM users").fetchone() == (1,)
