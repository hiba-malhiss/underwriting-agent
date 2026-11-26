"""Document controller: the HTTP layer for documents (like a Spring @RestController).

    POST /documents?type=requirement                     underwriting guidelines
    POST /documents?type=applicant&applicant_id=<uuid>   an applicant's documents
    GET  /documents?type=…                               same parameters
    GET  /documents/file?type=…&name=<stored name>       one document's content (e.g. a PDF)
    DELETE /documents?type=…&name=<stored name>          one document (name from the list)

Only HTTP here: read the request, call the service, shape the response. The rules and the
storage calls are in service.py. Errors are raised, not caught: core/error_handlers.py
turns them into HTTP responses for every route.

No authentication yet: keep this API local (don't expose it) until access control is added.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status

from app.documents.dependencies import get_document_service
from app.documents.schemas import DocumentListResponse, DocumentResponse
from app.documents.service import DocumentService
from app.documents.types import DocumentType

router = APIRouter(prefix="/documents", tags=["Documents"])

# `?type=` in the URL; named document_type in Python so it doesn't shadow the built-in type()
TypeParam = Annotated[DocumentType, Query(alias="type")]
Service = Annotated[DocumentService, Depends(get_document_service)]


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    document_type: TypeParam,
    file: UploadFile,
    service: Service,
    applicant_id: UUID | None = None,
) -> DocumentResponse:
    document = await service.upload(
        document_type, file.filename or "document", await file.read(), applicant_id
    )
    return DocumentResponse.from_stored(document)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    document_type: TypeParam, service: Service, applicant_id: UUID | None = None
) -> DocumentListResponse:
    documents = await service.list_documents(document_type, applicant_id)
    return DocumentListResponse(documents=[DocumentResponse.from_stored(d) for d in documents])


# The stored name contains "/" for applicant documents, so it's a query parameter, not a path
@router.get("/file")
async def download_document(
    document_type: TypeParam, name: str, service: Service, applicant_id: UUID | None = None
) -> Response:
    data, content_type = await service.download(document_type, name, applicant_id)
    # inline: the browser shows it (e.g. the guideline next to a rule) instead of saving it
    return Response(data, media_type=content_type, headers={"Content-Disposition": "inline"})


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_type: TypeParam, name: str, service: Service, applicant_id: UUID | None = None
) -> Response:
    await service.delete(document_type, name, applicant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
