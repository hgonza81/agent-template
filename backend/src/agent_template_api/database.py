from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase

from agent_template_api.settings import Settings, get_settings


class Base(DeclarativeBase):
    pass


def create_database_engine(settings: Settings | None = None) -> Engine:
    current_settings = settings or get_settings()
    return create_engine(
        current_settings.database_url.get_secret_value(),
        connect_args={"options": "-c timezone=UTC"},
        pool_pre_ping=True,
    )
