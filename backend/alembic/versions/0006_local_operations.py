"""Importación idempotente y configuración local de respaldos, aditiva."""
from alembic import op

revision = "0006_local_operations"
down_revision = "0005_reporting_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for sql in (
        """CREATE TABLE csv_imports (
            idempotency_key TEXT PRIMARY KEY CHECK(length(idempotency_key)=36),
            actor_id INTEGER NOT NULL REFERENCES users(id), source_hash TEXT NOT NULL,
            product_ids TEXT NOT NULL, created_at_utc TEXT NOT NULL)""",
        """CREATE TABLE maintenance_state (
            id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
            interval_hours INTEGER NOT NULL DEFAULT 24 CHECK(interval_hours BETWEEN 1 AND 168),
            retention INTEGER NOT NULL DEFAULT 7 CHECK(retention BETWEEN 1 AND 30),
            last_attempt INTEGER NOT NULL DEFAULT 0, last_success INTEGER NOT NULL DEFAULT 0,
            last_error TEXT, generation TEXT NOT NULL DEFAULT '')""",
        "INSERT INTO maintenance_state(id) VALUES(1)",
    ):
        op.execute(sql)


def downgrade() -> None:
    raise RuntimeError("No se admite downgrade destructivo de operaciones locales")
