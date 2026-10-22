"""F5 agrega solo un índice; preserva F4 y recupera DDL interrumpido."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from alembic import command
from app.infrastructure.schema import SchemaCompatibilityError
from app.main import create_app
from tests.test_reporting import seed

pytest_plugins = ("tests.test_sales_migrations",)


def test_f4_upgrade_preserves_rows_and_session_and_uses_index(f3_database):
    config, _, path, cookie = f3_database
    command.upgrade(config, '0004_checkout_history')
    seed(path, 13, '2026-01-01T03:00:00+00:00', user=7)
    with sqlite3.connect(path) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='alembic_version'")]
        before = {t: db.execute('SELECT * FROM ' + t).fetchall() for t in tables}
    with pytest.raises(SchemaCompatibilityError), TestClient(create_app(path)):
        pytest.fail('F5 debe rechazar esquema F4')
    command.upgrade(config, 'head')
    command.upgrade(config, 'head')
    with sqlite3.connect(path) as db:
        for t, rows in before.items():
            assert db.execute('SELECT * FROM ' + t).fetchall() == rows
        plan = db.execute("EXPLAIN QUERY PLAN SELECT COUNT(*),total_cents FROM sales WHERE status='COMPLETED' AND created_at_utc>=? AND created_at_utc<?", ('2026', '2027')).fetchall()
        assert 'SEARCH sales USING COVERING INDEX sales_report_date' in str(plan)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    with TestClient(create_app(path), base_url='http://127.0.0.1', headers={'cookie': f'pos_session={cookie}'}) as client:
        assert client.get('/api/auth/me').status_code == 200
        assert client.get('/api/reports/summary?period=custom&start=2026-01-01&end=2026-01-01').json()['current']['sales'] == '1'


def test_interrupted_index_rolls_back_and_retries(f3_database):
    config, scripts, path, _ = f3_database
    command.upgrade(config, '0004_checkout_history')
    with sqlite3.connect(path) as db:
        before = list(db.iterdump())
    file = scripts / 'versions/0005_reporting_indexes.py'
    original = file.read_text()
    file.write_text(original.replace('\n\ndef downgrade()', '\n    raise RuntimeError("interrupción F5")\n\ndef downgrade()'))
    with pytest.raises(RuntimeError, match='interrupción F5'):
        command.upgrade(config, 'head')
    with sqlite3.connect(path) as db:
        assert list(db.iterdump()) == before
    file.write_text(original)
    command.upgrade(config, 'head')
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0006_local_operations',)


def test_missing_report_index_refuses_startup(database):
    with sqlite3.connect(database) as db:
        db.execute('DROP INDEX sales_report_date')
    with pytest.raises(SchemaCompatibilityError), TestClient(create_app(database)):
        pytest.fail('No debe iniciar sin índice requerido')
