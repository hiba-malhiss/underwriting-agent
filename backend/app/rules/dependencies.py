"""Wiring for the rules module (dependency injection), like documents/dependencies.py.

- At startup, main.py creates the MySQL engine and its session factory once and keeps them in
  app.state (a shared connection pool, like a Spring DataSource).
- Per request, Depends builds the repository from that factory. It's cheap (it holds no
  connection until it runs a query), so controllers and services just declare it:

      repository: Annotated[RulebookRepository, Depends(get_rulebook_repository)]
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ServiceUnavailableError
from app.rules.repository import RulebookRepository


class DatabaseNotConfiguredError(ServiceUnavailableError):
    """MySQL isn't set up in .env. Answered with 503 and what to set."""

    def public_message(self) -> str:
        return str(self)


def get_db_sessions(request: Request) -> async_sessionmaker[AsyncSession]:
    sessions = request.app.state.db_sessions
    if sessions is None:
        raise DatabaseNotConfiguredError(
            "The database isn't configured. Set MYSQL_HOST and MYSQL_USER in .env."
        )
    return sessions


def get_rulebook_repository(
    sessions: Annotated[async_sessionmaker[AsyncSession], Depends(get_db_sessions)],
) -> RulebookRepository:
    return RulebookRepository(sessions)
