from collections.abc import Iterator
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agent_template_api.database import create_database_engine
from agent_template_api.models import Subscription
from agent_template_api.settings import Settings


@pytest.fixture(scope="module")
def database_session() -> Iterator[Session]:
    settings = Settings(
        _env_file=None,
        cors_allowed_origins=["http://127.0.0.1:5173"],
        database_url=(
            "postgresql+psycopg://agent_template:local-dev-only"
            "@127.0.0.1:5433/agent_template_test"
        ),
    )
    engine = create_database_engine(settings)
    if engine.url.database != "agent_template_test":
        raise RuntimeError(
            "Subscription model tests require the agent_template_test database"
        )

    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")

    with Session(engine) as session:
        assert session.execute(text("SHOW TIME ZONE")).scalar_one() == "UTC"
        yield session

    engine.dispose()


def test_subscription_generates_uuid_and_utc_start_time(
    database_session: Session,
) -> None:
    subscription = Subscription(
        identity_issuer="https://issuer.example.test",
        identity_subject=str(uuid4()),
    )
    database_session.add(subscription)
    database_session.flush()
    database_session.refresh(subscription)

    assert subscription.id is not None
    assert subscription.started_at.tzinfo is not None
    utc_offset = subscription.started_at.utcoffset()
    assert utc_offset is not None
    assert utc_offset.total_seconds() == 0

    database_session.rollback()


def test_subscription_identity_pair_is_unique(database_session: Session) -> None:
    identity_issuer = "https://issuer.example.test"
    identity_subject = str(uuid4())
    subscription = Subscription(
        identity_issuer=identity_issuer,
        identity_subject=identity_subject,
    )
    database_session.add(subscription)
    database_session.flush()

    with pytest.raises(IntegrityError):
        with database_session.begin_nested():
            database_session.add(
                Subscription(
                    identity_issuer=identity_issuer,
                    identity_subject=identity_subject,
                )
            )
            database_session.flush()

    database_session.rollback()
