from collections.abc import Iterator
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from pytest import MonkeyPatch
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from agent_template_api.models import Subscription
from agent_template_api.settings import get_settings

ADMIN_URL = (
    "postgresql+psycopg://agent_template:local-dev-only"
    "@127.0.0.1:5433/agent_template_test"
)
SCRATCH_PREFIX = "agent_template_test_migration_"


@pytest.fixture
def scratch_engine(monkeypatch: MonkeyPatch) -> Iterator[Engine]:
    """A throwaway database, so migrations always start from an empty schema."""
    name = f"{SCRATCH_PREFIX}{uuid4().hex[:12]}"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{name}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://127.0.0.1:5173"]')
    get_settings.cache_clear()
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()
        get_settings.cache_clear()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def test_migration_history_has_a_single_head() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    assert len(script.get_heads()) == 1


def test_migrations_upgrade_from_empty_database_and_match_models(
    scratch_engine: Engine,
) -> None:
    command.upgrade(Config("alembic.ini"), "head")

    assert "subscriptions" in inspect(scratch_engine).get_table_names()
    with scratch_engine.connect() as connection:
        diff = compare_metadata(
            MigrationContext.configure(connection), Subscription.metadata
        )
    assert diff == []


def test_migrations_downgrade_to_base_and_upgrade_again(
    scratch_engine: Engine,
) -> None:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    assert "subscriptions" not in inspect(scratch_engine).get_table_names()

    command.upgrade(config, "head")

    assert "subscriptions" in inspect(scratch_engine).get_table_names()
