"""Migraciones en una base aislada: baseline, upgrade aditivo y reaplicación."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_baseline_persists_and_identity_upgrade_is_additive(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, "LOCALAPPDATA": str(tmp_path)}
    command = [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade"]
    path = tmp_path / "GestionInteligentePOS" / "data" / "pos.db"
    for revision in ("0001_empty_baseline", "0001_empty_baseline", "head", "head"):
        subprocess.run(
            command + [revision], cwd=backend, env=env, check=True, capture_output=True, text=True
        )
        expected = "0006_local_operations" if revision == "head" else revision
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (expected,)
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            tables = {
                row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if revision == "0001_empty_baseline":
                assert tables == {"alembic_version"}
            else:
                assert tables == {
                    "alembic_version",
                    "users",
                    "sessions",
                    "bootstrap",
                    "audit_log",
                    "audit_events",
                    "categories",
                    "products",
                    "stock_movements",
                    "sales",
                    "sale_items",
                    "payments",
                    "csv_imports",
                    "maintenance_state",
                }


def test_failed_identity_migration_rolls_back_ddl_and_can_retry(tmp_path, monkeypatch):
    """Interrupción a mitad: sin tablas residuales, revisión intacta y reintento real."""
    import shutil

    import pytest
    from alembic.config import Config

    from alembic import command

    backend = Path(__file__).resolve().parents[1]
    migrations = tmp_path / "alembic"
    shutil.copytree(backend / "alembic", migrations)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(migrations))
    command.upgrade(config, "0001_empty_baseline")
    path = tmp_path / "GestionInteligentePOS/data/pos.db"
    migration = migrations / "versions/0002_identity.py"
    original = migration.read_text()
    migration.write_text(
        original.replace(
            "        op.execute(statement)",
            '        if statement.startswith("CREATE TABLE sessions"):\n'
            '            raise RuntimeError("interrupción simulada")\n'
            "        op.execute(statement)",
        )
    )
    with pytest.raises(RuntimeError, match="interrupción simulada"):
        command.upgrade(config, "head")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0001_empty_baseline",
        )
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [
            ("alembic_version",)
        ]
    migration.write_text(original)
    command.upgrade(config, "head")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0006_local_operations",
        )
        assert db.execute("SELECT COUNT(*) FROM users").fetchone() == (0,)


def test_autogenerate_refused_without_changing_files_or_data(database):
    backend = Path(__file__).resolve().parents[1]
    versions = backend / "alembic/versions"
    before_files = {file.name: file.read_bytes() for file in versions.glob("*.py")}
    with sqlite3.connect(database) as db:
        before_dump = list(db.iterdump())
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "revision",
            "--autogenerate",
            "-m",
            "unsafe",
        ],
        check=False,
        cwd=backend,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "does not provide a MetaData object" in result.stdout + result.stderr
    assert {file.name: file.read_bytes() for file in versions.glob("*.py")} == before_files
    with sqlite3.connect(database) as db:
        assert list(db.iterdump()) == before_dump
