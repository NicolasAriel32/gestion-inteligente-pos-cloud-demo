"""Construcción nativa reproducible (Linux prueba de empaquetado; Windows produce .exe)."""
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
version = tomllib.loads((root / 'backend/pyproject.toml').read_text())['project']['version']
if not (root / 'frontend/dist/index.html').is_file():
    raise SystemExit('Ejecutar npm ci / npm run build en frontend primero')
licenses = root / 'packaging/licenses'
licenses.mkdir(exist_ok=True)
# Solo licencias/metadata, nunca variables/credenciales del entorno.
for distribution in importlib.metadata.distributions():
    for path in distribution.files or []:
        if 'license' in str(path).lower() or 'copying' in str(path).lower():
            source = distribution.locate_file(path)
            if source.is_file() and source.stat().st_size < 1024*1024:
                destination = licenses / (distribution.metadata['Name'] + '-' + source.name)
                shutil.copyfile(source, destination)
subprocess.run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', str(root / 'packaging/pos.spec')], cwd=root, check=True)
bundle = root / 'dist/GestionInteligentePOS'
manifest = {'product_version': version, 'phase': 'F6 candidate', 'build_os': platform.platform(),
            'python': platform.python_version(), 'pyinstaller': importlib.metadata.version('pyinstaller'),
            'files': {str(p.relative_to(bundle)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(bundle.rglob('*')) if p.is_file()}}
(bundle / 'build-info.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Paquete candidato F6 generado:', bundle)
