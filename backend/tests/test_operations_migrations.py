"""0006: preservar F5, detener esquema anterior y recuperar DDL fallido."""
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from alembic import command
from app.infrastructure.schema import SchemaCompatibilityError
from app.main import create_app
from tests.test_reporting import seed

pytest_plugins = ('tests.test_sales_migrations',)


def test_upgrade_preserves_f5_rows_and_session(f3_database):
    config, _, path, cookie = f3_database
    command.upgrade(config, '0005_reporting_indexes')
    seed(path, 13, '2026-01-01T03:00:00+00:00', user=7)
    with closing(sqlite3.connect(path)) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='alembic_version'")]
        before = {t: db.execute('SELECT * FROM '+t).fetchall() for t in tables}
    with pytest.raises(SchemaCompatibilityError), TestClient(create_app(path)):
        pytest.fail('F6 rechaza esquema anterior')
    command.upgrade(config, 'head'); command.upgrade(config, 'head')
    with closing(sqlite3.connect(path)) as db:
        assert all(db.execute('SELECT * FROM '+t).fetchall() == rows for t, rows in before.items())
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    with TestClient(create_app(path), base_url='http://127.0.0.1', headers={'cookie': f'pos_session={cookie}'}) as client:
        assert client.get('/api/auth/me').status_code == 200
        assert client.get('/api/backups').status_code == 200


def test_interruption_rolls_back_and_retries(f3_database):
    config, scripts, path, _ = f3_database
    command.upgrade(config, '0005_reporting_indexes')
    with closing(sqlite3.connect(path)) as db:
        before = list(db.iterdump())
    file = scripts / 'versions/0006_local_operations.py'
    original = file.read_text()
    file.write_text(original.replace('        op.execute(sql)', '        if "maintenance_state" in sql:\n            raise RuntimeError("interrupción F6")\n        op.execute(sql)'))
    with pytest.raises(RuntimeError, match='interrupción F6'):
        command.upgrade(config, 'head')
    with closing(sqlite3.connect(path)) as db:
        assert list(db.iterdump()) == before
    file.write_text(original)
    command.upgrade(config, 'head')
    with closing(sqlite3.connect(path)) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0006_local_operations',)
