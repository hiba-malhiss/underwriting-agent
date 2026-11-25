"""The composition root: creates the shared clients, wires the modules, and starts the app.

It knows WHICH modules exist, not how they work: each module builds its own parts (see
documents/dependencies.py).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.error_handlers import register_error_handlers
from app.core.settings import settings
from app.documents.controller import router as documents_router
from app.documents.dependencies import create_document_indexers, create_document_stores
from app.infrastructure.azure_credential import azure_credential
from app.infrastructure.database import (
    create_mysql_engine,
    create_sessions,
    create_tables,
    is_reachable,
)
from app.infrastructure.document_reader import DocumentReader
from app.infrastructure.llm import LanguageModel
from app.rules.controller import router as rules_router


# startup => yield => shutdown
# app.state => store data across the app => access by request.app.state
@asynccontextmanager
async def lifespan(app: FastAPI):
    # One Azure identity for the whole app, shared by every Azure client
    credential = azure_credential(settings.azure_interactive_login, settings.azure_tenant_id)
    app.state.document_stores = create_document_stores(credential)
    app.state.document_indexers = create_document_indexers(credential)
    # Document Intelligence, when configured (reads guidelines and applicants' documents)
    app.state.document_reader = (
        DocumentReader.connect(settings.document_intelligence_endpoint, credential)
        if settings.document_intelligence_endpoint
        else None
    )
    # The language model, when configured (extracts rules and applicants' values)
    app.state.language_model = (
        LanguageModel.connect(
            settings.azure_openai_endpoint, settings.azure_openai_deployment, credential
        )
        if settings.azure_openai_endpoint
        else None
    )
    # MySQL, when configured: tables are created if missing (v1: no migrations yet)
    # app.state keeps the shared pool; repositories are built per request (rules/dependencies.py)
    app.state.database = None
    app.state.db_sessions = None
    if settings.mysql_host and settings.mysql_user:
        app.state.database = create_mysql_engine(
            settings.mysql_host, settings.mysql_database, settings.mysql_user, credential
        )
        await create_tables(app.state.database)
        app.state.db_sessions = create_sessions(app.state.database)
    yield
    if app.state.database is not None:
        await app.state.database.dispose()
    if app.state.document_reader is not None:
        await app.state.document_reader.close()
    if app.state.language_model is not None:
        await app.state.language_model.close()
    for store in app.state.document_stores.values():
        await store.close()
    for indexer in app.state.document_indexers.values():
        await indexer.close()
    await credential.close()


app = FastAPI(title="Health Insurance Underwriting Agent", lifespan=lifespan)
register_error_handlers(app)
app.include_router(documents_router)
app.include_router(rules_router)


@app.get("/health")
async def health():
    # "down": check the settings in .env, the containers, and the MySQL firewall (your IP)
    stores = app.state.document_stores
    database = app.state.database
    return {
        "status": "ok",
        "storage": {
            document_type: "up" if await store.is_reachable() else "down"
            for document_type, store in stores.items()
        },
        "database": (
            "not configured"
            if database is None
            else ("up" if await is_reachable(database) else "down")
        ),
    }
