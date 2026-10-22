"""Contrato mínimo de arranque: no migrar ni reparar datos automáticamente."""

from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

EXPECTED_REVISION = "0006_local_operations"
REQUIRED_COLUMNS = {
    "csv_imports": {"idempotency_key", "actor_id", "source_hash", "product_ids", "created_at_utc"},
    "maintenance_state": {"id", "enabled", "interval_hours", "retention", "last_attempt", "last_success", "last_error", "generation"},
    "sales": {"id", "idempotency_key", "request_hash", "user_id", "username_snapshot", "status", "total_cents", "created_at_utc", "voided_at_utc", "voided_by", "void_reason"},
    "sale_items": {"id", "sale_id", "product_id", "product_name_snapshot", "product_code_snapshot", "unit_price_cents", "quantity", "subtotal_cents"},
    "payments": {"id", "sale_id", "method", "amount_cents"},
    "categories": {"id", "name", "name_key", "is_active"},
    "products": {
        "id",
        "name",
        "code",
        "category_id",
        "price_cents",
        "cost_cents",
        "stock_quantity",
        "minimum_stock",
        "is_active",
        "created_at",
        "updated_at",
    },
    "stock_movements": {
        "id",
        "product_id",
        "movement_type",
        "quantity_delta",
        "stock_before",
        "stock_after",
        "performed_by",
        "reason",
        "request_key",
        "created_at_utc",
        "reference_type",
        "reference_id",
    },
    "audit_events": {
        "id",
        "actor_id",
        "action",
        "entity_type",
        "entity_id",
        "event_data",
        "created_at_utc",
    },
    "alembic_version": {"version_num"},
    "users": {"id", "username", "password_hash", "role", "is_active", "created_at"},
    "bootstrap": {"id", "token_hash", "expires_at", "completed"},
    "sessions": {"token_hash", "user_id", "expires_at"},
    "audit_log": {
        "id",
        "actor_id",
        "action",
        "entity_type",
        "entity_id",
        "event_data",
        "created_at_utc",
    },
}


class SchemaCompatibilityError(RuntimeError):
    """Base sin migrar, incompleta o de otra versión: no se habilita la aplicación."""


def verify_schema(engine: Engine) -> None:
    message = (
        "Esquema local incompatible. No se inició la aplicación. "
        "Verificá la versión instalada y el respaldo antes de ejecutar las migraciones. "
        "No borres la base ni cambies alembic_version manualmente."
    )
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            if not REQUIRED_COLUMNS.keys() <= set(inspector.get_table_names()):
                raise SchemaCompatibilityError(message)
            for table, expected in REQUIRED_COLUMNS.items():
                actual = {column["name"] for column in inspector.get_columns(table)}
                if not expected <= actual:
                    raise SchemaCompatibilityError(message)
            indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("sales")}
            if indexes.get("sales_report_date") != ["status", "created_at_utc", "id", "total_cents"]:
                raise SchemaCompatibilityError(message)
            revisions = connection.execute(text("SELECT version_num FROM alembic_version")).all()
            if revisions != [(EXPECTED_REVISION,)]:
                raise SchemaCompatibilityError(message)
    except SQLAlchemyError:
        raise SchemaCompatibilityError(message) from None
