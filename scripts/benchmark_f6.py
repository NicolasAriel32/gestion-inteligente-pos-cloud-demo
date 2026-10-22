"""Carga ficticia reproducible. No mide ni modifica la PC comercial."""
import json
import platform
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from app.bootstrap import prepare_setup
from app.infrastructure.migrations import upgrade_database
from app.main import create_app
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory(prefix='pos-f6-benchmark-') as folder:
    path = Path(folder) / 'data/pos.db'
    upgrade_database(path)
    secret = prepare_setup(path).read_text()
    with TestClient(create_app(path), base_url='http://127.0.0.1', headers={'origin': 'http://127.0.0.1:5173'}) as client:
        password = 'F6-benchmark-fictitious-42'
        assert client.post('/api/auth/setup', json={'username': 'owner', 'password': password, 'setup_token': secret}).status_code == 201
        csrf = client.post('/api/auth/login', json={'username': 'owner', 'password': password}).json()['csrf_token']
        def post(route, body):
            response = client.post('/api'+route, json=body, headers={'X-CSRF-Token': csrf})
            assert response.status_code == 200, (route, response.status_code)
            return response.json()
        csv = 'nombre;codigo;precio;stock_inicial;stock_minimo\n' + ''.join(f'Producto {i};{i:06};125,05;10;1\n' for i in range(500))
        start = time.perf_counter(); preview = post('/imports/products/preview', {'content': csv}); preview_ms = (time.perf_counter()-start)*1000
        start = time.perf_counter(); imported = post('/imports/products/confirm', {'content': csv, 'source_hash': preview['source_hash'], 'idempotency_key': str(uuid4()), 'reason': 'Carga ficticia de volumen'}); import_ms = (time.perf_counter()-start)*1000
        for i in range(1000):
            items = [{'product_id': imported['product_ids'][i % 500], 'quantity': 1}]
            quote = post('/sales/quote', {'items': items})
            sale = client.post('/api/sales', json={'items': items, 'quote_fingerprint': quote['quote_fingerprint'], 'idempotency_key': str(uuid4()), 'payment_method': 'CASH'}, headers={'X-CSRF-Token': csrf})
            assert sale.status_code == 201
        start = time.perf_counter(); report = client.get('/api/reports/summary').json(); report_ms = (time.perf_counter()-start)*1000
        assert report['current']['sales'] == '1000' and report['current']['revenue_cents'] == '12505000'
        start = time.perf_counter(); backup = post('/backups', {}); backup_ms = (time.perf_counter()-start)*1000
        start = time.perf_counter(); post('/backups/restore', {'backup_id': backup['id'], 'password': password, 'confirmation': 'RESTAURAR'}); restore_ms = (time.perf_counter()-start)*1000
        print(json.dumps({'os': platform.system(), 'products': 500, 'sales': 1000, 'database_bytes': path.stat().st_size,
                          'preview_ms': round(preview_ms, 2), 'import_ms': round(import_ms, 2), 'report_ms': round(report_ms, 2),
                          'backup_ms': round(backup_ms, 2), 'restore_ms': round(restore_ms, 2), 'includes_admin_reauthentication': True}))
