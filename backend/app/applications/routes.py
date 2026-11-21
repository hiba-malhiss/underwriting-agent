"""Application documents: upload a document to an application, and list its documents.

No authentication yet: keep this API local (don't expose it) until access control is added.
Applications aren't records yet (MySQL comes later), so an application id just groups its
documents.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status

from app.applications.schemas import DocumentListResponse, DocumentResponse
from app.applications.validation import DocumentRejectedError, accepted_content_type
from app.core.settings import settings
from app.storage.blob import BlobStore, ContainerNotFoundError, StorageError

router = APIRouter(prefix="/applications", tags=["Applications"])


def get_blob_store(request: Request) -> BlobStore:
    # Opened once at startup (see main.py) and shared by every request. Taken through a
    # dependency so every route gets it the same way, and a test can swap it for a fake.
    return request.app.state.blob_store


Store = Annotated[BlobStore, Depends(get_blob_store)]


@router.post(
    "/{application_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(application_id: UUID, file: UploadFile, store: Store) -> DocumentResponse:
    filename = file.filename or "document"
    data = await file.read()
    try:
        content_type = accepted_content_type(filename, len(data), settings.max_upload_mb * 1024**2)
        document = await store.upload(application_id, filename, data, content_type)
    except DocumentRejectedError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    except ContainerNotFoundError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except StorageError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Storage request failed") from error
    return DocumentResponse.from_stored(document)


@router.get("/{application_id}/documents", response_model=DocumentListResponse)
async def list_documents(application_id: UUID, store: Store) -> DocumentListResponse:
    try:
        documents = await store.list_documents(application_id)
    except ContainerNotFoundError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except StorageError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Storage request failed") from error
    return DocumentListResponse(documents=[DocumentResponse.from_stored(d) for d in documents])
