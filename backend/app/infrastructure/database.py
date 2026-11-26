"""MySQL access: one shared async engine for the app's lifetime.

No password anywhere: each NEW connection asks the shared Azure credential for a fresh Entra
token and uses it as the password (Azure Database for MySQL accepts Entra tokens). Locally that's
your browser login; on Azure, the app's Managed Identity. A token lasts about an hour, but it's
only checked when a connection opens, so open connections keep working; the pool recycles
connections every 30 minutes, so new ones always get a fresh token.

The identity must be a MySQL Entra user (the server's Entra admin, for now). Tables belong to
the features (e.g. rules/persistence/tables.py); they all share `Base`.
"""

import ssl

import aiomysql
from azure.core.credentials_async import AsyncTokenCredential
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# The Entra "audience" for Azure Database for MySQL / PostgreSQL tokens
MYSQL_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


class Base(DeclarativeBase):
    """Every table in the app derives from this, so create_tables can create them all."""


# engin manage connecting to database => get connection from engin
def create_mysql_engine(
    host: str, database: str, user: str, credential: AsyncTokenCredential
) -> AsyncEngine:
    ssl_context = ssl.create_default_context()  # Azure requires TLS; the token travels inside it

    async def connect():
        token = await credential.get_token(MYSQL_TOKEN_SCOPE)
        return await aiomysql.connect(
            host=host,
            user=user,
            password=token.token,
            db=database,
            ssl=ssl_context,
            charset="utf8mb4",
        )

    return create_async_engine(
        "mysql+aiomysql://",
        async_creator=connect,
        pool_pre_ping=True,  # check if connected before using it
        pool_recycle=1800,  # replace connection after 30 min
    )


def create_sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: rows stay readable after the transaction ends
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    """Create any missing tables (v1: no migrations yet; Alembic comes in v2). Existing tables
    and their data are left as they are."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def is_reachable(engine: AsyncEngine) -> bool:
    """The server answers and lets us in (for /health)."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:  # any failure means "down" here; the reason is in the server logs
        return False
