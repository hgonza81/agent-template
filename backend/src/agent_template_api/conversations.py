"""Server-owned conversation (provider thread) reference per subscription."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from agent_template_api.models import Subscription


def get_thread_id(engine: Engine, subscription_id: UUID) -> str | None:
    with Session(engine) as session:
        return session.execute(
            select(Subscription.foundry_thread_id).where(
                Subscription.id == subscription_id
            )
        ).scalar_one()


def store_thread_id(engine: Engine, subscription_id: UUID, thread_id: str) -> str:
    """Record the thread reference unless one exists; return the stored one."""
    with Session(engine) as session, session.begin():
        session.execute(
            update(Subscription)
            .where(
                Subscription.id == subscription_id,
                Subscription.foundry_thread_id.is_(None),
            )
            .values(foundry_thread_id=thread_id)
        )
        return (
            session.execute(
                select(Subscription.foundry_thread_id).where(
                    Subscription.id == subscription_id
                )
            ).scalar_one_or_none()
            or thread_id
        )
