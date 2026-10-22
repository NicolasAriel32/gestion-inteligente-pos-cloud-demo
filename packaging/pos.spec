# Construir desde raíz: python -m PyInstaller --clean --noconfirm packaging/pos.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / 'packaging/entry.py')],
    pathex=[str(root / 'backend')],
    datas=[(str(root / 'frontend/dist'), 'frontend'),
           (str(root / 'backend/alembic'), 'alembic'),
           (str(root / 'packaging/licenses'), 'licenses')]
          + collect_data_files('tzdata') + collect_data_files('alembic', includes=['templates/**/*']),
    hiddenimports=collect_submodules('app') + ['sqlalchemy.dialects.sqlite', 'argon2.low_level', 'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto', 'uvicorn.lifespan.on'],
    hookspath=[], runtime_hooks=[], excludes=['pytest', 'httpx', 'ruff'], noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name='GestionInteligentePOS',
          debug=False, strip=False, upx=False, console=True)
collection = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name='GestionInteligentePOS')
