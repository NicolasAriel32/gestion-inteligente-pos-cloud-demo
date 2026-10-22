"""Prueba automatizada Windows Server del instalador; no certifica Windows 11 limpio."""
import hashlib
import http.cookiejar
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
installer = next((root / 'dist/installer').glob('*-setup.exe'))
password = 'F6-fictitious-smoke-42'
steps = []

with tempfile.TemporaryDirectory(prefix='pos-win-smoke-') as temporary:
    folder = Path(temporary)
    install = folder / 'installed'
    env = dict(os.environ, LOCALAPPDATA=str(folder / 'profile'), PATH=os.path.join(os.environ['SystemRoot'], 'System32'))
    def install_candidate():
        subprocess.run([str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', f'/DIR={install}'], env=env, check=True, timeout=60)
    install_candidate(); steps.append('install_per_user')
    executable = install / 'GestionInteligentePOS.exe'
    subprocess.run([str(executable), '--prepare'], input='PREPARAR\n', env=env, encoding='utf-8', check=True, timeout=60)
    steps.append('prepare_explicit_without_python_node_on_PATH')
    secret = folder / 'profile/GestionInteligentePOS/config/setup-token.txt'
    process = None
    opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(path, body=None, csrf=None):
        request = Request('http://127.0.0.1:8765'+path, data=json.dumps(body).encode() if body is not None else None,
                          headers={'Origin': 'http://127.0.0.1:8765', 'Content-Type': 'application/json', **({'X-CSRF-Token': csrf} if csrf else {})})
        with opener.open(request, timeout=30) as response:
            return json.load(response)
    def start():
        child = subprocess.Popen([str(executable), '--no-browser'], env=env)
        for _ in range(200):
            if child.poll() is not None:
                raise RuntimeError('El ejecutable terminó antes de iniciar')
            try:
                if call('/api/health') == {'status': 'ok'}:
                    return child
            except (URLError, OSError):
                time.sleep(.1)
        child.terminate(); child.wait(timeout=10)
        raise RuntimeError('Ejecutable no disponible')
    try:
        process = start(); steps.append('start_packaged')
        subprocess.run([str(executable), '--no-browser'], env=env, check=True, timeout=20)
        steps.append('second_instance_excluded')
        call('/api/auth/setup', {'username': 'owner', 'password': password, 'setup_token': secret.read_text()})
        csrf = call('/api/auth/login', {'username': 'owner', 'password': password})['csrf_token']
        csv = 'nombre;codigo;precio;stock_inicial;stock_minimo\nPrueba;0001;1,25;3;1\n'
        preview = call('/api/imports/products/preview', {'content': csv}, csrf)
        imported = call('/api/imports/products/confirm', {'content': csv, 'source_hash': preview['source_hash'], 'reason': 'Carga ficticia', 'idempotency_key': str(uuid4())}, csrf)
        assert len(imported['product_ids']) == 1
        product_id = imported['product_ids'][0]
        cart = {'items': [{'product_id': product_id, 'quantity': 1}]}
        def buy():
            quote = call('/api/sales/quote', cart, csrf)
            return call('/api/sales', {**cart, 'quote_fingerprint': quote['quote_fingerprint'], 'payment_method': 'CASH', 'idempotency_key': str(uuid4())}, csrf)
        sale = buy()
        voided = buy()
        call(f"/api/sales/{voided['id']}/void", {'reason': 'Anulación ficticia'}, csrf)
        assert sale['total_cents'] == 125
        backup = call('/api/backups', {}, csrf)
        call('/api/stock/adjustments', {'product_id': product_id, 'quantity_delta': 5, 'reason': 'Cambio posterior ficticio', 'idempotency_key': str(uuid4())}, csrf)
        assert call('/api/backups/restore', {'backup_id': backup['id'], 'password': password, 'confirmation': 'RESTAURAR'}, csrf)['restored']
        csrf = call('/api/auth/login', {'username': 'owner', 'password': password})['csrf_token']
        assert call(f'/api/products/{product_id}')['stock_quantity'] == 2
        assert call(f"/api/sales/{sale['id']}")['total_cents'] == 125
        assert call(f"/api/sales/{voided['id']}")['status'] == 'VOIDED'
        assert call('/api/reports/summary')['current']['revenue_cents'] == '125'
        steps.append('import_sales_void_backup_restore_reports_and_reauthentication')
        call('/api/runtime/shutdown', {}, csrf); process.wait(timeout=15)
        assert process.returncode == 0
        steps.append('controlled_shutdown')
        database = folder / 'profile/GestionInteligentePOS/data/pos.db'
        before = hashlib.sha256(database.read_bytes()).hexdigest()
        private = folder / 'profile/GestionInteligentePOS'
        preserved = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in [secret, *(private / 'backups').glob('*.posbackup')]}
        assert len(preserved) >= 3  # secreto, respaldo manual y previo a restauración
        def check_preserved_files():
            assert all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest
                       for path, digest in preserved.items())
        install_candidate()
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before
        check_preserved_files()
        steps.append('reinstall_preserves_database_backups_and_config')
        process = start()
        csrf = call('/api/auth/login', {'username': 'owner', 'password': password})['csrf_token']
        assert call('/api/products')['items'][0]['code'] == '0001'
        call('/api/runtime/shutdown', {}, csrf); process.wait(timeout=15)
        before = hashlib.sha256(database.read_bytes()).hexdigest()
        subprocess.run([str(install / 'unins000.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], env=env, check=True, timeout=60)
        assert database.exists() and hashlib.sha256(database.read_bytes()).hexdigest() == before
        check_preserved_files()
        steps.append('uninstall_preserves_database_backups_and_config')
    finally:
        if process and process.poll() is None:
            process.terminate(); process.wait(timeout=15)
(root / 'dist/windows-smoke.json').write_text(json.dumps({'steps_passed': steps,
    'environment': 'GitHub hosted Windows Server; not a clean Windows 11 pilot',
    'child_PATH': 'Windows System32 only', 'physical_printer': 'not tested'}, indent=2), encoding='utf-8')
print('Windows candidate smoke checks passed:', len(steps))
