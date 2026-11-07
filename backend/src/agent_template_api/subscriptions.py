"""Idempotent provisioning of the single free subscription per identity."""

from sqlalchemy import select
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
        return session.execute(
            select(Subscription).where(
                Subscription.identity_issuer == identity.issuer,
                Subscription.identity_subject == identity.subject,
            )
        ).scalar_one()
