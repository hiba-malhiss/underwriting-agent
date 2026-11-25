"""Wiring for the documents module: what it needs, and how it's built (dependency injection).

- At startup, main.py calls create_document_stores (one store per document type, each on its
  own container) and create_document_indexers (the search indexer that reads each container,
  where one is set). Which is which is the documents module's business, not main's.
- Per request, FastAPI's Depends builds the service from those stores, like Spring autowiring:
  controller ← get_document_service ← get_stores.
"""

from typing import Annotated

from azure.core.credentials_async import AsyncTokenCredential
from fastapi import Depends, Request

from app.core.settings import settings
from app.documents.service import DocumentService
from app.documents.types import DocumentType
from app.infrastructure.search.indexer import IndexerRunner
from app.infrastructure.storage.blob import BlobStore


def create_document_stores(credential: AsyncTokenCredential) -> dict[DocumentType, BlobStore]:
    containers = {
        DocumentType.APPLICANT: settings.applicant_container,
        DocumentType.REQUIREMENT: settings.requirements_container,
    }
    return {
        document_type: BlobStore.connect(settings.azure_storage_account_url, container, credential)
        for document_type, container in containers.items()
    }


def create_document_indexers(
    credential: AsyncTokenCredential,
) -> dict[DocumentType, IndexerRunner]:
    """Only the document types with an indexer set in .env; none without a search endpoint."""
    if not settings.azure_search_endpoint:
        return {}
    indexer_names = {
        DocumentType.APPLICANT: settings.applicant_indexer,
        DocumentType.REQUIREMENT: settings.requirements_indexer,
    }
    return {
        document_type: IndexerRunner.connect(settings.azure_search_endpoint, name, credential)
        for document_type, name in indexer_names.items()
        if name
    }


def get_stores(request: Request) -> dict[DocumentType, BlobStore]:
    # Created once at startup (see main.py) and shared by every request
    return request.app.state.document_stores


def get_indexers(request: Request) -> dict[DocumentType, IndexerRunner]:
    # Created once at startup (see main.py) and shared by every request
    return request.app.state.document_indexers


def get_document_service(
    stores: Annotated[dict[DocumentType, BlobStore], Depends(get_stores)],
    indexers: Annotated[dict[DocumentType, IndexerRunner], Depends(get_indexers)],
) -> DocumentService:
    return DocumentService(stores, settings.max_upload_mb, indexers)
