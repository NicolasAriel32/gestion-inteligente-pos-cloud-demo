"""Puerto de administración local; HTTP no accede a SQLite ni a rutas de archivos."""
from typing import Protocol

from app.domain.catalog import Record


class MaintenancePersistence(Protocol):
    def status(self, token: str) -> Record: ...
    def download(self, token: str, backup_id: str) -> bytes: ...
    def create(self, token: str) -> Record: ...
    def configure(self, token: str, enabled: bool, interval_hours: int, retention: int) -> Record: ...
    def upload(self, token: str, content: str) -> Record: ...
    def restore(self, token: str, backup_id: str, password: str) -> Record: ...
    def automatic(self) -> None: ...


class MaintenanceService:
    def __init__(self, store: MaintenancePersistence):
        self.store = store

    def status(self, token: str) -> Record:
        return self.store.status(token)

    def download(self, token: str, backup_id: str) -> bytes:
        return self.store.download(token, backup_id)

    def create(self, token: str) -> Record:
        return self.store.create(token)

    def configure(self, token: str, enabled: bool, interval_hours: int, retention: int) -> Record:
        if not 1 <= interval_hours <= 168 or not 1 <= retention <= 30:
            from app.domain.identity import IdentityError
            raise IdentityError(422, "Frecuencia o retención fuera del rango admitido")
        return self.store.configure(token, enabled, interval_hours, retention)

    def upload(self, token: str, content: str) -> Record:
        return self.store.upload(token, content)

    def restore(self, token: str, backup_id: str, password: str) -> Record:
        return self.store.restore(token, backup_id, password)
