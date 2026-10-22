"""Venta y anulación: autorización, dinero e inventario en una sola unidad."""

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol

from app.application.identity import digest
from app.domain.catalog import MAX_INTEGER, Product, Record
from app.domain.identity import IdentityError, User
from app.domain.sales import PaymentMethod, RequestedItem, SaleStatus


class SalesUnit(Protocol):
    def session_user(self, token_hash: str, now: int) -> User: ...
    def product(self, product_id: int) -> Product | None: ...
    def change_stock(self, product_id: int, stock: int) -> None: ...
    def event(self, actor: User, action: str, entity: str, target: int, data: Record) -> None: ...
    def sale(self, sale_id: int) -> Record | None: ...
    def sale_by_key(self, key: str) -> Record | None: ...
    def sale_items(self, sale_id: int) -> list[Record]: ...
    def payment(self, sale_id: int) -> Record: ...
    def add_sale(self, actor: User, key: str, request_hash: str, total: int) -> int: ...
    def add_item(self, sale_id: int, item: Record) -> None: ...
    def add_payment(self, sale_id: int, method: str, total: int) -> None: ...
    def sale_movement(self, actor: User, product: Product, delta: int, sale_id: int, reason: str, kind: str) -> None: ...
    def void_sale(self, sale_id: int, actor: User, reason: str) -> None: ...
    def sales(self, user_id: int | None, status: str | None, limit: int, offset: int) -> Record: ...


class SalesPersistence(Protocol):
    def transaction(self, write: bool = False) -> AbstractContextManager[SalesUnit]: ...


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class SalesService:
    def __init__(self, store: SalesPersistence, clock: Callable[[], float], generation: Callable[[], str] = lambda: ""):
        self.store, self.clock, self.generation = store, clock, generation

    def actor(self, tx: SalesUnit, token: str) -> User:
        return tx.session_user(digest(token), int(self.clock()))

    @staticmethod
    def calculate(tx: SalesUnit, items: list[RequestedItem], generation: str = "") -> tuple[Record, list[Product]]:
        lines: list[Record] = []
        products: list[Product] = []
        total = 0
        for item in sorted(items, key=lambda item: item["product_id"]):
            product = tx.product(item["product_id"])
            if product is None or not product.is_active:
                raise IdentityError(409, "Un producto ya no está disponible; revisá el carrito")
            if product.stock_quantity < item["quantity"]:
                raise IdentityError(409, f"Stock insuficiente de {product.name}; revisá la cantidad")
            subtotal = product.price_cents * item["quantity"]
            total += subtotal
            if total > MAX_INTEGER:
                raise IdentityError(422, "El total excede el rango admitido")
            lines.append({
                "product_id": product.id, "product_name_snapshot": product.name,
                "product_code_snapshot": product.code, "unit_price_cents": product.price_cents,
                "quantity": item["quantity"], "subtotal_cents": subtotal,
            })
            products.append(product)
        return {"items": lines, "total_cents": total, "quote_fingerprint": fingerprint([lines, generation] if generation else lines)}, products

    def quote(self, token: str, items: list[RequestedItem]) -> Record:
        with self.store.transaction() as tx:
            self.actor(tx, token)
            return self.calculate(tx, items, self.generation())[0]

    @staticmethod
    def require_sale(tx: SalesUnit, sale_id: int, actor: User) -> Record:
        sale = tx.sale(sale_id)
        if sale is None:
            raise IdentityError(404, "Venta inexistente")
        if actor.role != "ADMIN" and sale["user_id"] != actor.id:
            raise IdentityError(403, "Solo podés consultar tus ventas")
        return sale

    @staticmethod
    def detail(tx: SalesUnit, sale: Record) -> Record:
        fields = ("id", "user_id", "username_snapshot", "status", "total_cents", "created_at_utc", "voided_at_utc", "voided_by", "void_reason")
        return {**{key: sale[key] for key in fields}, "items": tx.sale_items(sale["id"]), "payment": tx.payment(sale["id"])}

    def create(self, token: str, items: list[RequestedItem], method: PaymentMethod, key: str, quote: str) -> Record:
        with self.store.transaction(write=True) as tx:
            actor = self.actor(tx, token)
            request_hash = fingerprint([actor.id, sorted(items, key=lambda item: item["product_id"]), method, quote])
            previous = tx.sale_by_key(key)
            if previous:
                if previous["request_hash"] != request_hash or previous["user_id"] != actor.id:
                    raise IdentityError(409, "La clave de venta ya se usó con otros datos")
                return self.detail(tx, previous)
            calculated, products = self.calculate(tx, items, self.generation())
            if calculated["quote_fingerprint"] != quote:
                raise IdentityError(409, "El catálogo cambió o se restauró un respaldo; consultá Historial y revisá una nueva cotización antes de confirmar")
            sale_id = tx.add_sale(actor, key, request_hash, calculated["total_cents"])
            for line, product in zip(calculated["items"], products, strict=True):
                tx.add_item(sale_id, line)
                tx.sale_movement(actor, product, -line["quantity"], sale_id, f"Venta #{sale_id}", "SALE")
                tx.change_stock(product.id, product.stock_quantity - line["quantity"])
            tx.add_payment(sale_id, method, calculated["total_cents"])
            tx.event(actor, "SALE_COMPLETED", "sales", sale_id, {"total_cents": calculated["total_cents"], "payment_method": method})
            sale = tx.sale(sale_id)
            assert sale is not None
            return self.detail(tx, sale)

    def sale(self, token: str, sale_id: int) -> Record:
        with self.store.transaction() as tx:
            actor = self.actor(tx, token)
            return self.detail(tx, self.require_sale(tx, sale_id, actor))

    def sales(self, token: str, user_id: int | None, status: SaleStatus | None, limit: int, offset: int) -> Record:
        with self.store.transaction() as tx:
            actor = self.actor(tx, token)
            if actor.role != "ADMIN":
                if user_id is not None and user_id != actor.id:
                    raise IdentityError(403, "Solo podés consultar tus ventas")
                user_id = actor.id
            return tx.sales(user_id, status, limit, offset)

    def void(self, token: str, sale_id: int, reason: str) -> Record:
        with self.store.transaction(write=True) as tx:
            actor = self.actor(tx, token)
            if actor.role != "ADMIN":
                raise IdentityError(403, "Se requiere rol ADMIN")
            sale = self.require_sale(tx, sale_id, actor)
            if sale["status"] == "VOIDED":
                if sale["void_reason"] != reason:
                    raise IdentityError(409, "La venta ya está anulada con otro motivo")
                return self.detail(tx, sale)
            for item in tx.sale_items(sale_id):
                product = tx.product(item["product_id"])
                assert product is not None
                after = product.stock_quantity + item["quantity"]
                if after > MAX_INTEGER:
                    raise IdentityError(409, "El stock excedería el rango admitido; no se anuló la venta")
                tx.sale_movement(actor, product, item["quantity"], sale_id, reason, "VOID")
                tx.change_stock(product.id, after)
            tx.void_sale(sale_id, actor, reason)
            tx.event(actor, "SALE_VOIDED", "sales", sale_id, {"reason": reason})
            updated = tx.sale(sale_id)
            assert updated is not None
            return self.detail(tx, updated)
