"""Idempotent provisioning of the single free subscription per identity."""

from collections.abc import Awaitable, Callable

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from agent_template_api.auth import TokenIdentity
from agent_template_api.models import Subscription

MAX_EMAIL_LENGTH = 320


def normalize_email(email: str | None) -> str | None:
    """Display/contact snapshot only; never used to identify an account."""
    if email is None:
        return None
    normalized = email.strip().lower()
    if not normalized or len(normalized) > MAX_EMAIL_LENGTH or "@" not in normalized:
        return None
    return normalized


def provision_subscription(engine: Engine, identity: TokenIdentity) -> Subscription:
    """Return the caller's subscription, creating it on first use.

    Identity comes only from validated token claims. The unique
    (issuer, subject) constraint plus ON CONFLICT DO NOTHING makes concurrent
    first requests converge on one row: the losing transaction waits for the
    winner to commit, inserts nothing, and then reads the committed row.
    Email is display data only (see the refresh policy below).
    """
    with Session(engine, expire_on_commit=False) as session, session.begin():
        session.execute(
            insert(Subscription)
            .values(
                identity_issuer=identity.issuer,
                identity_subject=identity.subject,
                email_snapshot=normalize_email(identity.email),
            )
            .on_conflict_do_nothing(
                constraint="uq_subscriptions_identity_issuer_subject"
            )
        )
        subscription = session.execute(
            select(Subscription).where(
                Subscription.identity_issuer == identity.issuer,
                Subscription.identity_subject == identity.subject,
            )
        ).scalar_one()
        # Email refresh policy: a valid claim that differs updates the display
        # snapshot in place; a missing or invalid claim never clears it. The
        # lookup above never involves email, so a changed or shared email
        # cannot create, merge, or authorize an account.
        email = normalize_email(identity.email)
        if email is not None and email != subscription.email_snapshot:
            subscription.email_snapshot = email
        return subscription


async def delete_account(
    engine: Engine,
    identity: TokenIdentity,
    delete_thread: Callable[[str], Awaitable[None]],
) -> None:
    """Delete the caller's provider conversation, then their subscription.

    The subscription row is locked (`SELECT ... FOR UPDATE`) for the whole
    operation, so a concurrent first chat message cannot create a thread that
    would be orphaned. The provider is deleted first and the row only after
    that succeeded: a failure leaves the row (and its thread reference) in
    place, so the request can simply be retried and no conversation is left
    unreachable. Deleting an already-deleted account is a no-op.
    """
    connection = await run_in_threadpool(engine.connect)
    try:
        await run_in_threadpool(connection.begin)
        row = await run_in_threadpool(
            lambda: connection.execute(
                select(Subscription.id, Subscription.foundry_thread_id)
                .where(
                    Subscription.identity_issuer == identity.issuer,
                    Subscription.identity_subject == identity.subject,
                )
                .with_for_update()
            ).one_or_none()
        )
        if row is None:
            return
        if row.foundry_thread_id is not None:
            await delete_thread(row.foundry_thread_id)
        await run_in_threadpool(
            lambda: connection.execute(
                delete(Subscription).where(Subscription.id == row.id)
            )
        )
        await run_in_threadpool(connection.commit)
    finally:
        connection.close()
