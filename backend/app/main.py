from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.applications.routes import router as applications_router
from app.core.azure_credential import azure_credential
from app.core.settings import settings
from app.storage.blob import BlobStore


# startup => yeaild => shutdown
# app.state => store data across the app => access by request.app.state
@asynccontextmanager
async def lifespan(app: FastAPI):
    # One Azure identity for the app, shared by every Azure client (Storage now; Document
    # Intelligence, Foundry and AI Search later): one sign-in, one token cache
    credential = azure_credential(settings.azure_interactive_login, settings.azure_tenant_id)
    # One Blob Storage client for the app's lifetime, shared by every request
    app.state.blob_store = BlobStore.connect(
        settings.azure_storage_account_url, settings.storage_container, credential
    )
    yield
    await app.state.blob_store.close()
    await credential.close()


app = FastAPI(title="Health Insurance Underwriting Agent", lifespan=lifespan)


@app.get("/health")
async def health():
    # "down": check the storage settings in .env and that the container exists
    storage_up = await app.state.blob_store.is_reachable()
    return {"status": "ok", "storage": "up" if storage_up else "down"}


app.include_router(applications_router)
