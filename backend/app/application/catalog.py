"""Casos de uso de catálogo; toda autorización de escritura ocurre bajo el bloqueo."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict, replace
from typing import Protocol

from app.application.identity import digest
from app.domain.catalog import MAX_INTEGER, Category, Product, Record
from app.domain.identity import IdentityError, User


class CatalogUnit(Protocol):
    def session_user(self, token_hash: str, now: int) -> User: ...
    def category(self, category_id: int) -> Category | None: ...
    def categories(self, active_only: bool) -> list[Category]: ...
    def category_name_exists(self, name: str, excluding: int = 0) -> bool: ...
    def save_category(
        self, name: str, category_id: int | None = None, active: bool = True
    ) -> Category: ...
    def product(self, product_id: int) -> Product | None: ...
    def code_exists(self, code: str | None, excluding: int = 0) -> bool: ...
    def products(
        self,
        search: str,
        category_id: int | None,
        active_only: bool,
        low_stock: bool,
        limit: int,
        offset: int,
    ) -> Record: ...
    def save_product(self, data: Record, product_id: int | None = None) -> Product: ...
    def change_stock(self, product_id: int, stock: int) -> None: ...
    def movement(self, key: str) -> Record | None: ...
    def add_movement(
        self,
        actor: User,
        product: Product,
        delta: int,
        reason: str,
        kind: str,
        key: str | None = None,
    ) -> Record: ...
    def movements(self, product_id: int | None, limit: int, offset: int) -> Record: ...
    def event(self, actor: User, action: str, entity: str, target: int, data: Record) -> None: ...


class CatalogPersistence(Protocol):
    def transaction(self, write: bool = False) -> AbstractContextManager[CatalogUnit]: ...


class CatalogService:
    def __init__(self, store: CatalogPersistence, clock: Callable[[], float]):
        self.store, self.clock = store, clock

    def actor(self, tx: CatalogUnit, token: str, admin: bool = False) -> User:
        actor = tx.session_user(digest(token), int(self.clock()))
        if admin and actor.role != "ADMIN":
            raise IdentityError(403, "Se requiere rol ADMIN")
        return actor

    @staticmethod
    def require_product(tx: CatalogUnit, product_id: int) -> Product:
        product = tx.product(product_id)
        if product is None:
            raise IdentityError(404, "Producto inexistente")
        return product

    @staticmethod
    def check_category(tx: CatalogUnit, category_id: int | None) -> None:
        if category_id is not None:
            category = tx.category(category_id)
            if category is None or not category.is_active:
                raise IdentityError(409, "Elegí una categoría activa")

    def categories(self, token: str) -> list[Category]:
        with self.store.transaction() as tx:
            actor = self.actor(tx, token)
            return tx.categories(actor.role != "ADMIN")

    def save_category(self, token: str, data: Record, category_id: int | None = None) -> Category:
        with self.store.transaction(write=True) as tx:
            actor = self.actor(tx, token, admin=True)
            old = tx.category(category_id) if category_id else None
            if category_id and old is None:
                raise IdentityError(404, "Categoría inexistente")
            name = data.get("name", old.name if old else "")
            if tx.category_name_exists(name, category_id or 0):
                raise IdentityError(409, "La categoría ya existe")
            result = tx.save_category(
                name, category_id, data.get("is_active", old.is_active if old else True)
            )
            tx.event(
                actor,
                "CATEGORY_UPDATED" if old else "CATEGORY_CREATED",
                "categories",
                result.id,
                {"before": asdict(old) if old else None, "after": asdict(result)},
            )
            return result

    def products(
        self, token: str, search: str, category_id: int | None, active_only: bool,
        low_stock: bool, limit: int, offset: int,
    ) -> Record:
        with self.store.transaction() as tx:
            actor = self.actor(tx, token)
            result = tx.products(
                search, category_id, active_only or actor.role != "ADMIN", low_stock, limit, offset
            )
            result["items"] = [
                replace(p, cost_cents=None) if actor.role != "ADMIN" else p for p in result["items"]
            ]
            return result

    def product(self, token: str, product_id: int) -> Product:
        with self.store.transaction() as tx:
            actor = self.actor(tx, token)
            product = self.require_product(tx, product_id)
            if actor.role != "ADMIN" and not product.is_active:
                raise IdentityError(404, "Producto inexistente")
            return product if actor.role == "ADMIN" else replace(product, cost_cents=None)

    def create_product(self, token: str, data: Record) -> Product:
        with self.store.transaction(write=True) as tx:
            actor = self.actor(tx, token, admin=True)
            return self.create_in_transaction(tx, actor, data)

    @classmethod
    def create_in_transaction(cls, tx: CatalogUnit, actor: User, data: Record) -> Product:
        data = data.copy()
        initial = data.pop("initial_stock", 0)
        reason = data.pop("initial_reason", None)
        if initial and not reason:
            raise IdentityError(422, "Indicá el motivo del stock inicial")
        cls.check_category(tx, data.get("category_id"))
        if tx.code_exists(data.get("code")):
            raise IdentityError(409, "El código ya está en uso")
        product = tx.save_product({**data, "stock_quantity": 0})
        if initial:
            tx.add_movement(actor, product, initial, reason, "INITIAL")
            tx.change_stock(product.id, initial)
            product = cls.require_product(tx, product.id)
        tx.event(actor, "PRODUCT_CREATED", "products", product.id, {"after": asdict(product)})
        return product

    def update_product(self, token: str, product_id: int, changes: Record) -> Product:
        with self.store.transaction(write=True) as tx:
            actor = self.actor(tx, token, admin=True)
            old = self.require_product(tx, product_id)
            if "category_id" in changes and changes["category_id"] != old.category_id:
                self.check_category(tx, changes["category_id"])
            if "code" in changes and tx.code_exists(changes["code"], product_id):
                raise IdentityError(409, "El código ya está en uso")
            product = tx.save_product(changes, product_id)
            tx.event(
                actor,
                "PRODUCT_UPDATED",
                "products",
                product_id,
                {"before": asdict(old), "after": asdict(product)},
            )
            return product

    def adjust(self, token: str, product_id: int, delta: int, reason: str, key: str) -> Record:
        with self.store.transaction(write=True) as tx:
            actor = self.actor(tx, token, admin=True)
            previous = tx.movement(key)
            if previous:
                if (
                    previous["product_id"],
                    previous["quantity_delta"],
                    previous["reason"],
                    previous["performed_by"],
                ) != (product_id, delta, reason, actor.id):
                    raise IdentityError(409, "La clave de ajuste ya se usó con otros datos")
                return previous
            product = self.require_product(tx, product_id)
            if not product.is_active:
                raise IdentityError(409, "El producto está inactivo")
            after = product.stock_quantity + delta
            if after < 0:
                raise IdentityError(409, "Stock insuficiente para este ajuste")
            if after > MAX_INTEGER:
                raise IdentityError(422, "La cantidad excede el rango admitido")
            movement = tx.add_movement(actor, product, delta, reason, "ADJUSTMENT", key)
            tx.change_stock(product_id, after)
            tx.event(
                actor,
                "STOCK_ADJUSTED",
                "products",
                product_id,
                {
                    "movement_id": movement["id"],
                    "delta": delta,
                    "before": product.stock_quantity,
                    "after": after,
                    "reason": reason,
                },
            )
            return movement

    def movements(self, token: str, product_id: int | None, limit: int, offset: int) -> Record:
        with self.store.transaction() as tx:
            self.actor(tx, token, admin=True)
            return tx.movements(product_id, limit, offset)
