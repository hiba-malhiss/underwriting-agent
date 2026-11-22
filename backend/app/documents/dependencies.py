"""Wiring for the documents module: what it needs, and how it's built (dependency injection).

- At startup, main.py calls create_document_stores: one store per document type, each on its
  own container. Which container is which is the documents module's business, not main's.
- Per request, FastAPI's Depends builds the service from those stores, like Spring autowiring:
  controller ← get_document_service ← get_stores.
"""

from typing import Annotated

from azure.core.credentials_async import AsyncTokenCredential
from fastapi import Depends, Request

from app.core.settings import settings
from app.documents.service import DocumentService
from app.documents.types import DocumentType
from app.infrastructure.storage.blob import BlobStore
from app.infrastructure.storage.file_store import FileStore


def create_document_stores(credential: AsyncTokenCredential) -> dict[DocumentType, FileStore]:
    containers = {
        DocumentType.APPLICANT: settings.applicant_container,
        DocumentType.REQUIREMENT: settings.requirements_container,
    }
    return {
        document_type: BlobStore.connect(settings.azure_storage_account_url, container, credential)
        for document_type, container in containers.items()
    }


def get_stores(request: Request) -> dict[DocumentType, FileStore]:
    # Created once at startup (see main.py) and shared by every request
    return request.app.state.document_stores


def get_document_service(
    stores: Annotated[dict[DocumentType, FileStore], Depends(get_stores)],
) -> DocumentService:
    return DocumentService(stores, settings.max_upload_mb)
