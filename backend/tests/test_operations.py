"""F6 sobre SQLite temporal real: importación, backup WAL y restauración."""
import base64
import io
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest

from app.domain.identity import IdentityError
from app.infrastructure.backups import atomic_json, validate_snapshot
from app.main import create_app
from tests.conftest import PASSWORD, login
from tests.test_catalog import write
from tests.test_sales import buy, intent, stock_product

CSV = 'nombre;codigo;precio;stock_inicial;stock_minimo\nAlfajor importado;00001;1250,50;5;1\nAgua importada;;0.29;2;0\n'


def preview(client, csrf, content=CSV):
    return write(client, csrf, '/api/imports/products/preview', {'content': content})


def attempt(client, csrf, content=CSV):
    p = preview(client, csrf, content)
    assert p.status_code == 200, p.text
    return {'content': content, 'source_hash': p.json()['source_hash'], 'idempotency_key': str(uuid4()), 'reason': 'Carga inicial de prueba'}


def make_backup(client, csrf):
    r = write(client, csrf, '/api/backups', {})
    assert r.status_code == 200, r.text
    return r.json()


def restore(client, csrf, backup_id, password=PASSWORD):
    return write(client, csrf, '/api/backups/restore', {'backup_id': backup_id, 'password': password, 'confirmation': 'RESTAURAR'})


def test_import_preview_exact_atomic_and_replayed_without_codes(admin, database):
    client, csrf = admin
    body = attempt(client, csrf)
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT COUNT(*) FROM products').fetchone() == (0,)
    r = write(client, csrf, '/api/imports/products/confirm', body)
    assert r.status_code == 200, r.text
    assert len(r.json()['product_ids']) == 2
    assert write(client, csrf, '/api/imports/products/confirm', body).json()['replayed'] is True
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT code,price_cents,stock_quantity FROM products ORDER BY id').fetchall() == [('00001', 125050, 5), (None, 29, 2)]
        assert db.execute("SELECT COUNT(*) FROM stock_movements WHERE movement_type='INITIAL'").fetchone() == (2,)
        assert db.execute("SELECT COUNT(*) FROM audit_events WHERE action='CSV_IMPORTED'").fetchone() == (1,)
    assert write(client, csrf, '/api/imports/products/confirm', {**body, 'reason': 'Otro motivo de carga'}).status_code == 409
    assert preview(client, csrf).json()['errors'][0]['message'].startswith('Código ya existente')


@pytest.mark.parametrize('row', ['Mal;1;0.001;1;0', 'Mal;1;-1;1;0', 'Mal;1;1;1.5;0', 'Mal;1;1;9007199254740992;0', 'Mal;1;90071992547409.92;0;0', ';1;1;0;0', 'Mal;1;1;0'])
def test_invalid_csv_rows_never_write(admin, database, row):
    client, csrf = admin
    content = 'nombre;codigo;precio;stock_inicial;stock_minimo\n' + row
    p = preview(client, csrf, content)
    assert p.status_code == 200 and len(p.json()['errors']) == 1
    body = {'content': content, 'source_hash': p.json()['source_hash'], 'idempotency_key': str(uuid4()), 'reason': 'Carga inicial'}
    assert write(client, csrf, '/api/imports/products/confirm', body).status_code == 422
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT COUNT(*) FROM products').fetchone() == (0,)


@pytest.mark.parametrize('content', ['', 'nombre;codigo;precio;stock_inicial;stock_minimo\n', 'a,b,c\n1,2,3', 'nombre;codigo;precio;stock_inicial;stock_minimo\n"mal', 'nombre;codigo;precio;stock_inicial;stock_minimo\n' + 'A;;1;0;0\n'*501, 'x'*1048577], ids=['empty', 'no_rows', 'headers', 'quotes', 'row_limit', 'size_limit'])
def test_csv_bounds_and_malformed(admin, content):
    client, csrf = admin
    assert preview(client, csrf, content).status_code == 422


def test_import_duplicate_changed_file_concurrent_and_mid_failure(admin, database, monkeypatch):
    client, csrf = admin
    duplicate = CSV.replace('Agua importada;;', 'Agua importada;00001;')
    assert preview(client, csrf, duplicate).json()['errors']
    body = attempt(client, csrf)
    assert write(client, csrf, '/api/imports/products/confirm', {**body, 'content': CSV+'Otro;;1;0;0\n'}).status_code == 409
    from app.infrastructure.importing import ImportTransaction
    original = ImportTransaction.record_import
    def fail(*args, **kwargs):
        raise OSError('fallo al sellar importación')
    monkeypatch.setattr(ImportTransaction, 'record_import', fail)
    with pytest.raises(OSError):
        write(client, csrf, '/api/imports/products/confirm', body)
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT COUNT(*) FROM products').fetchone() == (0,)
        assert db.execute('SELECT COUNT(*) FROM stock_movements').fetchone() == (0,)
    monkeypatch.setattr(ImportTransaction, 'record_import', original)
    barrier = Barrier(2)
    def send(_):
        barrier.wait()
        return write(client, csrf, '/api/imports/products/confirm', body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, range(2)))
    assert all(r.status_code == 200 for r in results)
    assert results[0].json()['product_ids'] == results[1].json()['product_ids']
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT COUNT(*) FROM products').fetchone() == (2,)


def test_backup_restore_preserves_history_and_revokes_sessions(admin, database):
    client, csrf = admin
    p = stock_product(client, csrf)
    sale = buy(client, csrf, p).json()
    # Preservar también una anulación y atribución histórica.
    voided = buy(client, csrf, p).json()
    write(client, csrf, f"/api/sales/{voided['id']}/void", {'reason': 'Error de prueba'})
    report = client.get('/api/reports/summary').json()['current']
    backup = make_backup(client, csrf)
    uncertain = intent(client, csrf, [{'product_id': p['id'], 'quantity': 1}])
    buy(client, csrf, p)
    assert restore(client, csrf, backup['id']).status_code == 200
    assert client.get('/api/auth/me').status_code == 401
    csrf = login(client)
    assert client.get('/api/reports/summary').json()['current'] == report
    assert client.get(f"/api/sales/{sale['id']}").json() == sale
    assert client.get(f"/api/sales/{voided['id']}").json()['status'] == 'VOIDED'
    # Un intento posterior a la copia no se confirma automáticamente al restaurar.
    assert write(client, csrf, '/api/sales', uncertain).status_code == 409
    state = client.get('/api/backups').json()
    assert any(b['kind'] == 'pre_restore' for b in state['backups'])
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT stock_quantity FROM products').fetchone() == (4,)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []


def test_restore_reauth_upload_and_corrupt_rejection_leave_db_unchanged(admin, database):
    client, csrf = admin
    backup = make_backup(client, csrf)
    downloaded = client.get(f"/api/backups/{backup['id']}/download")
    assert downloaded.status_code == 200 and downloaded.content[:2] == b'PK'
    uploaded = write(client, csrf, '/api/backups/upload', {'content_base64': base64.b64encode(downloaded.content).decode()})
    assert uploaded.status_code == 200 and uploaded.json()['kind'] == 'uploaded'
    before = client.get('/api/auth/me').json()['user']
    assert restore(client, csrf, backup['id'], 'Incorrect-password-42').status_code == 403
    assert write(client, csrf, '/api/backups/restore', {'backup_id': backup['id'], 'password': PASSWORD, 'confirmation': 'NO'}).status_code == 422
    assert write(client, csrf, '/api/backups/upload', {'content_base64': 'bad!!!'}).status_code == 422
    assert write(client, csrf, '/api/backups/upload', {'content_base64': base64.b64encode(b'not a backup').decode()}).status_code == 422
    assert client.get('/api/auth/me').json()['user'] == before
    files = client.app.state.files
    damaged = files.path(backup['id'])
    damaged.write_bytes(b'broken')
    assert restore(client, csrf, backup['id']).status_code == 422
    assert client.get('/api/auth/me').status_code == 200


def test_restore_failure_recovers_previous_and_interruption_blocks_startup(admin, database, monkeypatch):
    client, csrf = admin
    backup = make_backup(client, csrf)
    stock_product(client, csrf)
    import app.infrastructure.maintenance as module
    real = module.copy_database
    def fail_after_copy(source, dest):
        real(source, dest)
        if source.name == 'source.db':
            raise OSError('interrupción inducida')
    monkeypatch.setattr(module, 'copy_database', fail_after_copy)
    assert restore(client, csrf, backup['id']).status_code == 503
    csrf = login(client)
    assert client.get('/api/products').json()['total'] == 1
    assert not client.app.state.files.journal.exists()
    # Journal durable equivale al estado observable dejado por terminación del proceso.
    previous = make_backup(client, csrf)
    files = client.app.state.files
    atomic_json(files.journal, {'previous_id': previous['id'], 'source_id': backup['id']})
    assert client.get('/api/health').status_code == 503
    from fastapi.testclient import TestClient
    with pytest.raises(RuntimeError, match='Restauración interrumpida'), TestClient(create_app(database)):
        pytest.fail('No debe habilitarse con journal pendiente')
    with pytest.raises(IdentityError, match="misma cuenta ADMIN"):
        client.app.state.maintenance.store.recover_interrupted('owner', 'Incorrect-password-42')
    assert files.journal.exists()
    monkeypatch.setattr(module, 'copy_database', real)
    client.app.state.maintenance.store.recover_interrupted('owner', PASSWORD)
    assert client.get('/api/health').status_code == 200
    csrf = login(client)
    assert client.get('/api/products').json()['total'] == 1


def test_backup_with_active_wal_and_concurrent_writes(admin, database):
    client, csrf = admin
    product = stock_product(client, csrf, stock=50)
    # Mantener conexión lectora para que el WAL permanezca activo durante la copia.
    with closing(sqlite3.connect(database)) as held:
        held.execute('BEGIN')
        held.execute('SELECT * FROM products').fetchall()
        barrier = Barrier(2)
        def backup_worker():
            barrier.wait()
            return make_backup(client, csrf)
        def sales_worker():
            barrier.wait()
            for _ in range(4):
                assert buy(client, csrf, product).status_code == 201
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(backup_worker)
            writer = pool.submit(sales_worker)
            backup = future.result(); writer.result()
        held.rollback()
    files = client.app.state.files
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / 'snapshot.db'
        files.unpack(files.path(backup['id']).read_bytes(), target)
        validate_snapshot(target)
        with closing(sqlite3.connect(target)) as db:
            sales = db.execute('SELECT COUNT(*) FROM sales').fetchone()[0]
            stock = db.execute('SELECT stock_quantity FROM products').fetchone()[0]
            assert sales + stock == 50
            assert db.execute('SELECT COUNT(*) FROM payments').fetchone()[0] == sales


def test_automatic_retention_and_failure_status(admin, monkeypatch):
    client, csrf = admin
    make_backup(client, csrf)
    assert client.put('/api/backups/settings', json={'enabled': True, 'interval_hours': 1, 'retention': 2}, headers={'X-CSRF-Token': csrf}).status_code == 200
    store = client.app.state.maintenance.store
    now = [int(store.clock())]
    store.clock = lambda: now[0]
    for _ in range(4):
        store.automatic(); now[0] += 3601
    entries = store.files.entries()
    assert len([b for b in entries if b['kind'] == 'automatic']) == 2
    assert len([b for b in entries if b['kind'] == 'manual']) == 1
    def fail(*args, **kwargs):
        raise OSError('No revelar este contenido sensible')
    monkeypatch.setattr(store.files, 'create', fail)
    store.automatic()
    state = store.state()
    assert state['last_error'] and 'sensible' not in state['last_error']
    assert state['last_attempt'] == now[0]


def test_operations_permissions_csrf_body_bounds(admin):
    client, csrf = admin
    backup = make_backup(client, csrf)
    assert client.post('/api/backups', json={}).status_code == 403
    assert client.post('/api/imports/products/preview', content=b'x' * (2*1024*1024+1), headers={'content-type': 'application/json', 'X-CSRF-Token': csrf}).status_code == 413
    write(client, csrf, '/api/employees', {'username': 'worker', 'password': PASSWORD})
    csrf = login(client, 'worker')
    for path in ['/api/backups', f"/api/backups/{backup['id']}/download"]:
        assert client.get(path).status_code == 403
    assert preview(client, csrf).status_code == 403
    assert write(client, csrf, '/api/backups', {}).status_code == 403
    assert restore(client, csrf, backup['id']).status_code == 403
    client.cookies.clear()
    assert client.get('/api/backups').status_code == 401


def test_backup_rejects_extra_schema_and_archive_paths(admin):
    client, csrf = admin
    files = client.app.state.files
    backup = make_backup(client, csrf)
    contents = files.path(backup['id']).read_bytes()
    with zipfile.ZipFile(io.BytesIO(contents)) as z:
        db = z.read('pos.db'); manifest = z.read('manifest.json')
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, 'w') as z:
        z.writestr('../pos.db', db); z.writestr('manifest.json', manifest)
    assert write(client, csrf, '/api/backups/upload', {'content_base64': base64.b64encode(bad.getvalue()).decode()}).status_code == 422
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / 'tampered.db'; target.write_bytes(db)
        with closing(sqlite3.connect(target)) as con:
            con.execute('CREATE TABLE unexpected(secret TEXT)'); con.commit()
        with pytest.raises(IdentityError, match='incompatible'):
            validate_snapshot(target)
