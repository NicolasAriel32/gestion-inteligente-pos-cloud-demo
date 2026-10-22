"""Snapshots SQLite Backup API y contenedor acotado; nunca copiar DB/WAL vivos."""
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import threading
import time
import zipfile
from contextlib import closing
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from uuid import UUID, uuid4

from app.domain.identity import IdentityError
from app.infrastructure.migrations import upgrade_database
from app.infrastructure.schema import EXPECTED_REVISION

MAX_BACKUP = 32 * 1024 * 1024
_schema_lock = threading.Lock()


def atomic_replace(source: Path, destination: Path) -> None:
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        kernel.MoveFileExW.restype = wintypes.BOOL
        if not kernel.MoveFileExW(str(source), str(destination), 1 | 8):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.replace(source, destination)
        descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_replace(Path(temporary), path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def signature(connection: sqlite3.Connection) -> list:
    return connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY type,name").fetchall()


@lru_cache(maxsize=1)
def _canonical() -> list:
    with tempfile.TemporaryDirectory(prefix='pos-schema-') as folder:
        path = Path(folder) / 'data' / 'pos.db'
        upgrade_database(path)
        with closing(sqlite3.connect(path)) as connection:
            return signature(connection)


def validate_snapshot(path: Path, current: bool = True) -> str:
    if not path.is_file() or path.stat().st_size > MAX_BACKUP:
        raise IdentityError(422, "Respaldo inexistente o mayor a 32 MiB")
    try:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)) as connection:
            connection.execute('PRAGMA trusted_schema=OFF')
            deadline = time.monotonic() + 10
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
            if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)] or connection.execute('PRAGMA foreign_key_check').fetchone():
                raise IdentityError(422, "Respaldo con errores de integridad")
            revisions = connection.execute('SELECT version_num FROM alembic_version').fetchall()
            if len(revisions) != 1:
                raise IdentityError(422, "Revisión de respaldo inválida")
            if current:
                with _schema_lock:
                    expected = _canonical()
                if revisions != [(EXPECTED_REVISION,)] or signature(connection) != expected:
                    raise IdentityError(422, "Respaldo incompatible con esta versión o estructura")
            return revisions[0][0]
    except sqlite3.Error as exc:
        raise IdentityError(422, "El archivo no es un respaldo SQLite válido") from exc


def copy_database(source: Path, destination: Path) -> None:
    # Destino nuevo para backup; al restaurar debe estar drenado por MaintenanceGate.
    deadline = time.monotonic() + 30
    def progress(status: int, remaining: int, total: int) -> None:
        if time.monotonic() > deadline:
            raise IdentityError(503, "La copia superó el tiempo admitido; reintentá")
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst, pages=128, progress=progress, sleep=0.01)
    if os.name != 'nt':
        destination.chmod(0o600)


class BackupFiles:
    def __init__(self, database: Path):
        self.database = database.resolve()
        self.root = self.database.parent.parent if self.database.parent.name == 'data' else self.database.parent
        self.directory = self.root / 'backups'
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.journal = self.root / 'config' / 'restore-pending.json'
        self.lock = threading.RLock()

    def path(self, backup_id: str) -> Path:
        try:
            name = str(UUID(backup_id))
        except ValueError as exc:
            raise IdentityError(422, "Identificador de respaldo inválido") from exc
        path = self.directory / f'{name}.posbackup'
        if path.is_symlink():
            raise IdentityError(422, "No se admiten enlaces como respaldo")
        return path

    @staticmethod
    def unpack(data: bytes, destination: Path) -> dict:
        if len(data) > MAX_BACKUP + 65536:
            raise IdentityError(422, "El respaldo supera 32 MiB")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sorted(archive.namelist()) != ['manifest.json', 'pos.db']:
                    raise ValueError('members')
                if archive.getinfo('pos.db').file_size > MAX_BACKUP or archive.getinfo('manifest.json').file_size > 4096:
                    raise ValueError('size')
                manifest = json.loads(archive.read('manifest.json'))
                payload = archive.read('pos.db')
                if not isinstance(manifest, dict) or manifest.get('format') != 1 or manifest.get('sha256') != hashlib.sha256(payload).hexdigest():
                    raise ValueError('manifest')
                if any(not isinstance(manifest.get(key), str) for key in ['schema', 'created_at_utc', 'sha256', 'kind', 'product_version']):
                    raise ValueError('metadata')
                datetime.fromisoformat(manifest['created_at_utc'])
                destination.write_bytes(payload)
                if os.name != 'nt':
                    destination.chmod(0o600)
                revision = validate_snapshot(destination)
                if manifest.get('schema') != revision:
                    raise ValueError('schema')
                return manifest
        except (ValueError, KeyError, zipfile.BadZipFile, RuntimeError, OSError) as exc:
            raise IdentityError(422, "Contenedor de respaldo inválido o dañado") from exc

    def create(self, kind: str = 'manual', current: bool = True) -> dict:
        with self.lock, tempfile.TemporaryDirectory(dir=self.directory, prefix='.snapshot-') as folder:
            snapshot = Path(folder) / 'pos.db'
            copy_database(self.database, snapshot)
            revision = validate_snapshot(snapshot, current=current)
            data = snapshot.read_bytes()
            backup_id = str(uuid4())
            manifest = {'format': 1, 'schema': revision, 'created_at_utc': datetime.now(UTC).isoformat(),
                        'sha256': hashlib.sha256(data).hexdigest(), 'kind': kind, 'id': backup_id,
                        'product_version': '0.5.1'}
            temporary = Path(folder) / 'container'
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED) as archive:
                archive.write(snapshot, 'pos.db')
                archive.writestr('manifest.json', json.dumps(manifest))
            with temporary.open('rb+') as stream:
                os.fsync(stream.fileno())
            atomic_replace(temporary, self.path(backup_id))
            if os.name != 'nt':
                self.path(backup_id).chmod(0o600)
            return {**manifest, 'size_bytes': self.path(backup_id).stat().st_size}

    def inspect(self, backup_id: str) -> dict:
        path = self.path(backup_id)
        if not path.exists() or path.stat().st_size > MAX_BACKUP + 65536:
            raise IdentityError(404, "Respaldo no disponible")
        with tempfile.TemporaryDirectory(dir=self.directory, prefix='.inspect-') as folder:
            manifest = self.unpack(path.read_bytes(), Path(folder) / 'pos.db')
        return {**manifest, 'id': backup_id, 'size_bytes': path.stat().st_size}

    def entries(self, limit: int | None = 100) -> list[dict]:
        with self.lock:
            paths = sorted(self.directory.glob('*.posbackup'), key=lambda p: p.stat().st_mtime, reverse=True)
            result = []
            for path in paths[:limit] if limit is not None else paths:
                if path.is_symlink():
                    continue
                try:
                    UUID(path.stem)
                except ValueError:
                    continue
                try:
                    # Listado lee metadatos acotados; contenido se verifica al restaurar/descargar.
                    with zipfile.ZipFile(path) as archive:
                        if archive.getinfo('manifest.json').file_size > 4096:
                            raise ValueError('manifest size')
                        manifest = json.loads(archive.read('manifest.json'))
                        if any(not isinstance(manifest.get(k), str) for k in ['created_at_utc', 'kind', 'schema']):
                            raise ValueError('metadata')
                    result.append({**manifest, 'id': path.stem, 'size_bytes': path.stat().st_size})
                except (ValueError, KeyError, zipfile.BadZipFile, OSError):
                    result.append({'id': path.stem, 'kind': 'invalid', 'created_at_utc': '', 'schema': '', 'size_bytes': path.stat().st_size})
            return result

    def upload(self, data: bytes) -> dict:
        with self.lock, tempfile.TemporaryDirectory(dir=self.directory, prefix='.upload-') as folder:
            snapshot = Path(folder) / 'pos.db'
            manifest = self.unpack(data, snapshot)
            backup_id = str(uuid4())
            manifest.update(id=backup_id, kind='uploaded')
            temporary = Path(folder) / 'container'
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED) as archive:
                archive.write(snapshot, 'pos.db')
                archive.writestr('manifest.json', json.dumps(manifest))
            with temporary.open('rb+') as stream:
                os.fsync(stream.fileno())
            atomic_replace(temporary, self.path(backup_id))
            if os.name != 'nt':
                self.path(backup_id).chmod(0o600)
            return self.inspect(backup_id)

    def retain_automatic(self, count: int) -> None:
        with self.lock:
            entries = [e for e in self.entries(limit=None) if e['kind'] == 'automatic']
            for entry in entries[count:]:
                self.path(entry['id']).unlink(missing_ok=True)
