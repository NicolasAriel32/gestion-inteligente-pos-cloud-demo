"""Administración de respaldos/restore con autorización y aprobación explícitas."""
import base64
import binascii
import json
import logging
import sqlite3
import tempfile
import threading
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.application.identity import digest
from app.domain.identity import IdentityError, User
from app.infrastructure.backups import BackupFiles, atomic_json, copy_database, validate_snapshot
from app.infrastructure.catalog import CatalogTransaction, now
from app.infrastructure.identity import IdentityStore
from app.infrastructure.passwords import ArgonPasswords


class MaintenanceStore:
    def __init__(self, engine: Engine, files: BackupFiles, clock: Callable[[], float]):
        self.engine, self.files, self.clock = engine, files, clock
        self.store = IdentityStore(engine)
        self.operation = threading.RLock()

    def admin(self, token: str) -> User:
        with self.store.transaction() as tx:
            actor = tx.session_user(digest(token), int(self.clock()))
            if actor.role != 'ADMIN':
                raise IdentityError(403, "Se requiere rol ADMIN")
            return actor

    def event(self, actor: User, action: str, data: dict) -> None:
        with self.store.transaction(write=True) as tx:
            CatalogTransaction(tx.connection).event(actor, action, 'maintenance', 0, data)

    def state(self) -> dict:
        with self.engine.connect() as db:
            return dict(db.execute(text('SELECT * FROM maintenance_state WHERE id=1')).mappings().one())

    def generation(self) -> str:
        return self.state()['generation']

    def status(self, token: str) -> dict:
        self.admin(token)
        return {'settings': self.state(), 'backups': self.files.entries()}

    def configure(self, token: str, enabled: bool, interval_hours: int, retention: int) -> dict:
        with self.operation, self.store.transaction(write=True) as tx:
            actor = tx.session_user(digest(token), int(self.clock()))
            if actor.role != 'ADMIN':
                raise IdentityError(403, "Se requiere rol ADMIN")
            tx.execute('UPDATE maintenance_state SET enabled=:enabled,interval_hours=:hours,retention=:retention WHERE id=1',
                       enabled=int(enabled), hours=interval_hours, retention=retention)
            CatalogTransaction(tx.connection).event(actor, 'BACKUP_SETTINGS_CHANGED', 'maintenance', 0,
                                                    {'enabled': enabled, 'interval_hours': interval_hours, 'retention': retention})
        return self.state()

    def create(self, token: str) -> dict:
        actor = self.admin(token)
        with self.operation:
            result = self.files.create()
            self.event(actor, 'BACKUP_CREATED', {'backup_id': result['id']})
            return result

    def automatic(self) -> None:
        with self.operation:
            state = self.state()
            timestamp = int(self.clock())
            if not state['enabled'] or timestamp - state['last_attempt'] < state['interval_hours'] * 3600:
                return
            with self.engine.begin() as db:
                db.execute(text('UPDATE maintenance_state SET last_attempt=:now WHERE id=1'), {'now': timestamp})
            try:
                self.files.create('automatic')
                self.files.retain_automatic(state['retention'])
                with self.engine.begin() as db:
                    db.execute(text('UPDATE maintenance_state SET last_success=:now,last_error=NULL WHERE id=1'), {'now': timestamp})
            except (OSError, sqlite3.Error, IdentityError, SQLAlchemyError, ValueError) as exc:
                logging.getLogger(__name__).warning("BACKUP_FAILED: %s", type(exc).__name__)
                with self.engine.begin() as db:
                    db.execute(text("UPDATE maintenance_state SET last_error='No se pudo crear el respaldo automático; revisá espacio y permisos' WHERE id=1"))

    def download(self, token: str, backup_id: str) -> bytes:
        self.admin(token)
        with self.operation, self.files.lock:
            self.files.inspect(backup_id)
            return self.files.path(backup_id).read_bytes()

    def upload(self, token: str, content: str) -> dict:
        actor = self.admin(token)
        try:
            data = base64.b64decode(content, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise IdentityError(422, 'Archivo de respaldo inválido') from exc
        with self.operation:
            entry = self.files.upload(data)
            self.event(actor, 'BACKUP_UPLOADED', {'backup_id': entry['id']})
            return entry

    @staticmethod
    def credentials(path: Path, username: str, password: str) -> User:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            row = db.execute("SELECT id,username,password_hash FROM users WHERE role='ADMIN' AND is_active=1 AND username=?", (username,)).fetchone()
        if row is None or not ArgonPasswords().verify(row[2], password):
            raise IdentityError(403, 'Se requiere la misma cuenta ADMIN y contraseña vigente en el respaldo')
        return User(row[0], row[1], 'ADMIN', True)

    def finalize_restore(self, actor: User, backup_id: str, action: str) -> None:
        with self.store.transaction(write=True) as tx:
            tx.execute('DELETE FROM sessions')
            tx.execute('UPDATE bootstrap SET token_hash=NULL')
            tx.execute('UPDATE maintenance_state SET generation=:generation WHERE id=1', generation=str(uuid4()))
            CatalogTransaction(tx.connection).event(actor, action, 'maintenance', 0, {'backup_id': backup_id})

    def restore(self, token: str, backup_id: str, password: str) -> dict:
        # El caller HTTP mantiene gate exclusivo y drena solicitudes/scheduler.
        actor = self.admin(token)
        with self.operation, self.files.lock:
            self.credentials(self.files.database, actor.username, password)
            self.files.inspect(backup_id)
            with tempfile.TemporaryDirectory(dir=self.files.directory, prefix='.restore-') as folder:
                source = Path(folder) / 'source.db'
                self.files.unpack(self.files.path(backup_id).read_bytes(), source)
                restored_actor = self.credentials(source, actor.username, password)
                previous = self.files.create('pre_restore')
                atomic_json(self.files.journal, {'previous_id': previous['id'], 'source_id': backup_id, 'created_at_utc': now()})
                self.engine.dispose()
                try:
                    copy_database(source, self.files.database)
                    self.check_restored_database()
                    self.finalize_restore(restored_actor, backup_id, 'BACKUP_RESTORED')
                except Exception as exc:
                    # Restituir snapshot previo; si también falla, journal conserva bloqueo de arranque.
                    fallback = Path(folder) / 'previous.db'
                    self.files.unpack(self.files.path(previous['id']).read_bytes(), fallback)
                    self.engine.dispose()
                    copy_database(fallback, self.files.database)
                    self.check_restored_database()
                    self.finalize_restore(actor, previous['id'], 'RESTORE_ROLLED_BACK')
                    self.files.journal.unlink()
                    raise IdentityError(503, 'No se completó la restauración. Se recuperó el estado previo; volvé a ingresar') from exc
                self.files.journal.unlink()
                return {'restored': True, 'previous_backup_id': previous['id']}

    def check_restored_database(self) -> None:
        # Sacar snapshot para validar sin ignorar un WAL del destino vivo.
        with tempfile.TemporaryDirectory(dir=self.files.directory, prefix='.check-') as folder:
            snapshot = Path(folder) / 'check.db'
            copy_database(self.files.database, snapshot)
            validate_snapshot(snapshot)

    def recover_interrupted(self, username: str, password: str) -> None:
        if not self.files.journal.exists():
            raise IdentityError(409, 'No hay una restauración interrumpida')
        journal = json.loads(self.files.journal.read_text())
        previous_id = journal['previous_id']
        with tempfile.TemporaryDirectory(dir=self.files.directory, prefix='.recover-') as folder:
            source = Path(folder) / 'previous.db'
            self.files.unpack(self.files.path(previous_id).read_bytes(), source)
            actor = self.credentials(source, username, password)
            self.engine.dispose()
            copy_database(source, self.files.database)
            self.check_restored_database()
            self.finalize_restore(actor, previous_id, 'RESTORE_RECOVERED')
            self.files.journal.unlink()
