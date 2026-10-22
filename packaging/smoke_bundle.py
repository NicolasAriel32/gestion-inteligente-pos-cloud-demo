"""Ejercicio real del ejecutable nativo, con datos temporales y PATH vacío."""
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


def smoke_bundle(executable: Path, profile: Path) -> list[str]:
    env = dict(os.environ, LOCALAPPDATA=str(profile), PATH='')
    password = 'F6-fictitious-bundle-42'
    prepared = subprocess.run([str(executable), '--prepare'], input='PREPARAR\n', env=env, text=True, capture_output=True, check=False, timeout=30)
    assert prepared.returncode == 0, prepared.stderr
    steps = ['prepare_PATH_empty']
    root = profile / 'GestionInteligentePOS'
    opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(path, body=None, csrf=None):
        request = Request('http://127.0.0.1:8765'+path, data=json.dumps(body).encode() if body is not None else None,
                          headers={'Origin': 'http://127.0.0.1:8765', 'Content-Type': 'application/json', **({'X-CSRF-Token': csrf} if csrf else {})})
        with opener.open(request, timeout=30) as response:
            return json.load(response)
    process = subprocess.Popen([str(executable), '--no-browser'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for _ in range(150):
            if process.poll() is not None:
                raise RuntimeError('El paquete terminó antes de iniciar')
            try:
                if call('/api/health') == {'status': 'ok'}:
                    break
            except (URLError, OSError):
                time.sleep(.1)
        else:
            raise RuntimeError('Paquete no disponible')
        again = subprocess.run([str(executable), '--no-browser'], env=env, capture_output=True, check=False, timeout=15)
        assert again.returncode == 0
        steps.append('start_and_single_instance')
        call('/api/auth/setup', {'username': 'owner', 'password': password, 'setup_token': (root / 'config/setup-token.txt').read_text()})
        csrf = call('/api/auth/login', {'username': 'owner', 'password': password})['csrf_token']
        content = 'nombre;codigo;precio;stock_inicial;stock_minimo\nPrueba empaquetada;00001;1,25;3;0\n'
        preview = call('/api/imports/products/preview', {'content': content}, csrf)
        imported = call('/api/imports/products/confirm', {'content': content, 'source_hash': preview['source_hash'], 'idempotency_key': str(uuid4()), 'reason': 'Carga ficticia'}, csrf)
        product_id = imported['product_ids'][0]
        cart = {'items': [{'product_id': product_id, 'quantity': 1}]}
        quote = call('/api/sales/quote', cart, csrf)
        sale = call('/api/sales', {**cart, 'quote_fingerprint': quote['quote_fingerprint'], 'payment_method': 'CASH', 'idempotency_key': str(uuid4())}, csrf)
        assert sale['total_cents'] == 125
        steps.append('import_and_checkout')
        backup = call('/api/backups', {}, csrf)
        call('/api/stock/adjustments', {'product_id': product_id, 'quantity_delta': 5, 'reason': 'Cambio posterior', 'idempotency_key': str(uuid4())}, csrf)
        assert call('/api/backups/restore', {'backup_id': backup['id'], 'password': password, 'confirmation': 'RESTAURAR'}, csrf)['restored']
        csrf = call('/api/auth/login', {'username': 'owner', 'password': password})['csrf_token']
        assert call(f'/api/products/{product_id}')['stock_quantity'] == 2
        assert call('/api/reports/summary')['current']['revenue_cents'] == '125'
        steps.append('backup_restore_stock_sales_reports')
        call('/api/runtime/shutdown', {}, csrf)
        process.wait(timeout=15)
        assert process.returncode == 0
        steps.append('controlled_shutdown')
    finally:
        if process.poll() is None:
            process.terminate(); process.wait(timeout=15)
    return steps


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    executable = root / 'dist/GestionInteligentePOS' / ('GestionInteligentePOS.exe' if os.name == 'nt' else 'GestionInteligentePOS')
    with tempfile.TemporaryDirectory(prefix='pos-bundle-smoke-') as folder:
        steps = smoke_bundle(executable, Path(folder))
    report = {'platform': os.name, 'PATH': 'empty in child', 'steps_passed': steps, 'windows11_clean': 'not tested'}
    (root / 'dist/bundle-smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
