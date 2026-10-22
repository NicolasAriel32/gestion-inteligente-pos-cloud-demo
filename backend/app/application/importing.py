"""Previsualización sin escribir y confirmación atómica/idempotente."""
import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol

from app.application.catalog import CatalogService, CatalogUnit
from app.application.identity import digest
from app.domain.catalog import Record
from app.domain.identity import IdentityError
from app.domain.importing import parse_csv


class ImportUnit(CatalogUnit, Protocol):
    def previous_import(self, key: str) -> Record | None: ...
    def record_import(self, key: str, actor: int, source_hash: str, ids: list[int]) -> None: ...


class ImportPersistence(Protocol):
    def transaction(self, write: bool = False) -> AbstractContextManager[ImportUnit]: ...


class ImportService:
    def __init__(self, store: ImportPersistence, clock: Callable[[], float], generation: Callable[[], str] = lambda: ""):
        self.store, self.clock, self.generation = store, clock, generation

    def preview(self, token: str, content: str) -> Record:
        with self.store.transaction() as tx:
            actor = tx.session_user(digest(token), int(self.clock()))
            if actor.role != 'ADMIN':
                raise IdentityError(403, "Se requiere rol ADMIN")
            result = parse_csv(content)
            result['source_hash'] = hashlib.sha256((result['source_hash'] + '\n' + self.generation()).encode()).hexdigest()
            for row in result['rows']:
                if tx.code_exists(row['code']):
                    result['errors'].append({"row": row['row'], "message": "Código ya existente; solo se admiten altas nuevas"})
            return result

    def confirm(self, token: str, content: str, key: str, source_hash: str, reason: str) -> Record:
        with self.store.transaction(write=True) as tx:
            actor = tx.session_user(digest(token), int(self.clock()))
            if actor.role != 'ADMIN':
                raise IdentityError(403, "Se requiere rol ADMIN")
            parsed = parse_csv(content)
            bound_hash = hashlib.sha256((parsed['source_hash'] + '\n' + self.generation()).encode()).hexdigest()
            if bound_hash != source_hash:
                raise IdentityError(409, "El archivo cambió; revisá otra vista previa")
            previous = tx.previous_import(key)
            # Motivo forma parte de identidad, además del contenido.
            request_hash = hashlib.sha256((source_hash + '\n' + reason).encode()).hexdigest()
            if previous:
                if previous['actor_id'] != actor.id or previous['source_hash'] != request_hash:
                    raise IdentityError(409, "La clave de importación ya se usó con otros datos")
                return {"product_ids": json.loads(previous['product_ids']), "replayed": True}
            if parsed['errors']:
                raise IdentityError(422, "Corregí todos los errores del CSV antes de importar")
            ids = []
            for row in parsed['rows']:
                data = {k: v for k, v in row.items() if k != 'row'}
                product = CatalogService.create_in_transaction(tx, actor, {**data, "initial_reason": reason})
                ids.append(product.id)
            tx.record_import(key, actor.id, request_hash, ids)
            tx.event(actor, "CSV_IMPORTED", "csv_imports", 0, {"count": len(ids), "source_hash": source_hash})
            return {"product_ids": ids, "replayed": False}
