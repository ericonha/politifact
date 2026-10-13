"""Confere se o banco está na última migração.

Evita o erro confuso "column ... does not exist" quando o código é mais novo
que o banco: os jobs param com uma mensagem que diz o que fazer.
"""

from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.db import engine

_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


class SchemaOutdated(RuntimeError):
    pass


@lru_cache
def _head() -> str | None:
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_ALEMBIC_INI.parent / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def current_revision() -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def schema_status() -> tuple[str | None, str | None]:
    """(revisão do banco, revisão mais nova do código)."""
    return current_revision(), _head()


def ensure_schema_current() -> None:
    current, head = schema_status()
    if current != head:
        raise SchemaOutdated(
            f"Banco na migração {current}, código espera {head}. "
            "Rode `docker compose up -d --build` para aplicar as migrações."
        )
