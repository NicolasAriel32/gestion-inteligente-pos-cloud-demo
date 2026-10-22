"""Runtime real local, recursos estáticos acotados y arranque único."""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from fastapi.testclient import TestClient

from app.infrastructure.schema import EXPECTED_REVISION
from app.main import create_app
from app.runtime import InstanceLock
from tests.conftest import PASSWORD


def test_static_assets_are_separate_from_data(database, tmp_path):
    root = tmp_path / 'frontend'
    (root / 'assets').mkdir(parents=True)
    (root / 'licenses').mkdir()
    (root / 'index.html').write_text('<html>POS local</html>')
    (root / 'assets' / 'sample.js').write_text('void 0')
    (root / 'licenses' / 'OFL.txt').write_text('OFL')
    with TestClient(create_app(database, root), base_url='http://127.0.0.1') as client:
        assert client.get('/').status_code == 200
        assert client.get('/assets/sample.js').status_code == 200
        assert client.get('/licenses/OFL.txt').status_code == 200
        for url in ['/data/pos.db', '/.env', '/api/not-found', '/assets/../../data/pos.db']:
            assert client.get(url).status_code == 404
        assert client.get('/', headers={'host': 'evil.example'}).status_code == 400


def test_instance_lock_has_real_cross_process_exclusion(tmp_path):
    path = tmp_path / 'instance.lock'
    lock = InstanceLock(path)
    assert lock.acquire()
    script = 'from pathlib import Path; from app.runtime import InstanceLock; import sys; lock=InstanceLock(Path(sys.argv[1])); acquired=lock.acquire(); lock.release(); sys.exit(2 if acquired else 0)'
    blocked = subprocess.run([sys.executable, '-c', script, str(path)], capture_output=True, check=False)
    assert blocked.returncode == 0
    lock.release()
    available = subprocess.run([sys.executable, '-c', script, str(path)], capture_output=True, check=False)
    assert available.returncode == 2


def test_launcher_prepare_start_second_instance_and_shutdown(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    frontend = backend.parent / 'frontend/dist'
    assert frontend.joinpath('index.html').exists(), 'Ejecutar npm run build antes de test_runtime'
    env = dict(os.environ, LOCALAPPDATA=str(tmp_path))
    prepared = subprocess.run([sys.executable, '-m', 'app.runtime', '--prepare'], input='PREPARAR\n', cwd=backend, env=env, text=True, capture_output=True, check=False)
    assert prepared.returncode == 0, prepared.stderr
    path = tmp_path / 'GestionInteligentePOS/data/pos.db'
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(path)) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == (EXPECTED_REVISION,)
    token = (path.parent.parent / 'config/setup-token.txt').read_text()
    opener = build_opener(ProxyHandler({}))
    process = subprocess.Popen([sys.executable, '-m', 'app.runtime', '--no-browser'], cwd=backend, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise AssertionError('Launcher terminó antes de estar disponible')
            try:
                with opener.open('http://127.0.0.1:8765/api/health', timeout=.5) as response:
                    if response.status == 200:
                        break
            except (URLError, OSError):
                time.sleep(.1)
        else:
            raise AssertionError('Runtime no inició')
        with opener.open('http://127.0.0.1:8765/') as response:
            assert b'<html' in response.read()
        again = subprocess.run([sys.executable, '-m', 'app.runtime', '--no-browser'], cwd=backend, env=env, capture_output=True, text=True, check=False)
        assert again.returncode == 0 and 'ya está iniciada' in again.stdout
        import http.cookiejar
        from urllib.request import HTTPCookieProcessor, Request
        jar = http.cookiejar.CookieJar()
        authenticated = build_opener(ProxyHandler({}), HTTPCookieProcessor(jar))
        def post(route, body, csrf=None):
            req = Request('http://127.0.0.1:8765/api'+route, data=json.dumps(body).encode(), headers={'content-type': 'application/json', 'origin': 'http://127.0.0.1:8765', **({'X-CSRF-Token': csrf} if csrf else {})})
            with authenticated.open(req) as response:
                return json.load(response)
        post('/auth/setup', {'username': 'owner', 'password': PASSWORD, 'setup_token': token})
        session = post('/auth/login', {'username': 'owner', 'password': PASSWORD})
        assert post('/runtime/shutdown', {}, session['csrf_token']) == {'stopping': True}
        process.wait(timeout=10)
        assert process.returncode == 0
    finally:
        if process.poll() is None:
            process.terminate(); process.wait(timeout=10)


def test_launcher_occupied_port_does_not_kill_owner(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    with socket.socket() as occupied:
        if os.name != 'nt':
            occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        occupied.bind(('127.0.0.1', 8765)); occupied.listen(1)
        result = subprocess.run([sys.executable, '-m', 'app.runtime', '--no-browser'], cwd=backend,
                                env=dict(os.environ, LOCALAPPDATA=str(tmp_path)), capture_output=True, text=True, check=False)
        assert result.returncode == 1 and 'ocupado' in result.stderr
        assert occupied.getsockname()[1] == 8765
