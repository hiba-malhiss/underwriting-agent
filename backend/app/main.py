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


# startup => yield => shutdown
# app.state => store data across the app => access by request.app.state
@asynccontextmanager
async def lifespan(app: FastAPI):
    # One Azure identity for the whole app, shared by every Azure client
    credential = azure_credential(settings.azure_interactive_login, settings.azure_tenant_id)
    app.state.document_stores = create_document_stores(credential)
    app.state.document_indexers = create_document_indexers(credential)
    yield
    for store in app.state.document_stores.values():
        await store.close()
    for indexer in app.state.document_indexers.values():
        await indexer.close()
    await credential.close()


app = FastAPI(title="Health Insurance Underwriting Agent", lifespan=lifespan)
register_error_handlers(app)
app.include_router(documents_router)


@app.get("/health")
async def health():
    # "down": check the storage settings in .env and that the containers exist
    stores = app.state.document_stores
    return {
        "status": "ok",
        "storage": {
            document_type: "up" if await store.is_reachable() else "down"
            for document_type, store in stores.items()
        },
    }
