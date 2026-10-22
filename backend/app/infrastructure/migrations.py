"""Mismo árbol Alembic en fuente y binario; preparación siempre explícita."""
from pathlib import Path

from alembic.config import Config

from alembic import command


def upgrade_database(path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config()
    config.set_main_option("script_location", str(root / 'alembic'))
    config.attributes['db_path'] = path
    command.upgrade(config, 'head')
