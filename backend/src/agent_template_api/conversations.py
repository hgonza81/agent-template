"""Server-owned conversation (provider thread) reference per subscription."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Select, select, update
from sqlalchemy.engine import Engine

from agent_template_api.models import Subscription


def _thread_query(subscription_id: UUID) -> Select[tuple[str | None]]:
    return select(Subscription.foundry_thread_id).where(
        Subscription.id == subscription_id
    )


def _read_thread_id(engine: Engine, subscription_id: UUID) -> str | None:
    with engine.connect() as connection:
        return connection.execute(_thread_query(subscription_id)).scalar_one()


async def ensure_thread_id(
    engine: Engine,
    subscription_id: UUID,
    create_thread: Callable[[], Awaitable[str]],
) -> str:
    """Return the subscription's thread reference, creating it exactly once.

    The common case is an unlocked read. On first use the subscription row is
    locked (`SELECT ... FOR UPDATE`) while the provider thread is created and
    its reference stored in the same transaction, so concurrent first requests
    wait and then reuse the winner's thread instead of creating extras. If the
    provider call or the commit fails, the transaction rolls back and no
    reference is stored; a later request retries. Lookups and updates are
    always scoped by subscription ID, which the server derives from the
    validated identity.
    """
    existing = await run_in_threadpool(_read_thread_id, engine, subscription_id)
    if existing is not None:
        return existing

    connection = await run_in_threadpool(engine.connect)
    try:
        await run_in_threadpool(connection.begin)
        locked = await run_in_threadpool(
            lambda: connection.execute(
                _thread_query(subscription_id).with_for_update()
            ).scalar_one()
        )
        if locked is not None:
            return locked
        created = await create_thread()
        await run_in_threadpool(
            lambda: connection.execute(
                update(Subscription)
                .where(Subscription.id == subscription_id)
                .values(foundry_thread_id=created)
            )
        )
        await run_in_threadpool(connection.commit)
        return created
    finally:
        # Closing rolls back anything uncommitted and releases the row lock.
        connection.close()
