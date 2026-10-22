"""Importación y catálogo comparten transacción serializada."""
import json
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine

from app.domain.catalog import Record
from app.infrastructure.catalog import CatalogTransaction, now
from app.infrastructure.identity import IdentityStore


class ImportTransaction(CatalogTransaction):
    def previous_import(self, key: str) -> Record | None:
        return self.row("SELECT * FROM csv_imports WHERE idempotency_key=:key", key=key)

    def record_import(self, key: str, actor: int, source_hash: str, ids: list[int]) -> None:
        self.execute("INSERT INTO csv_imports VALUES(:key,:actor,:hash,:ids,:now)", key=key,
                     actor=actor, hash=source_hash, ids=json.dumps(ids), now=now())


class ImportStore:
    def __init__(self, engine: Engine):
        self.identity = IdentityStore(engine)

    @contextmanager
    def transaction(self, write: bool = False) -> Iterator[ImportTransaction]:
        with self.identity.transaction(write) as tx:
            yield ImportTransaction(tx.connection)
