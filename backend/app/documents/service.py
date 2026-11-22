"""Document service: the business rules for documents (like a Spring @Service).

Checks who a document belongs to, which formats and sizes are accepted, how it's named and
whether it replaces an older version, then stores it.

Plain Python on purpose: no FastAPI (that's the controller and dependencies.py) and no Azure (it
works with any FileStore). So it's easy to test, and can be reused outside HTTP (e.g. a job).
"""

from uuid import UUID

from app.documents.types import DOCUMENT_CONFIGS, DocumentType
from app.documents.validation import accepted_content_type
from app.infrastructure.storage.file_store import FileStore, StoredDocument


class DocumentService:
    def __init__(self, stores: dict[DocumentType, FileStore], max_upload_mb: int):
        self._stores = stores
        self._max_bytes = max_upload_mb * 1024 * 1024

    async def upload(
        self,
        document_type: DocumentType,
        filename: str,
        data: bytes,
        applicant_id: UUID | None,
    ) -> StoredDocument:
        config = DOCUMENT_CONFIGS[document_type]
        config.validate_applicant_id(applicant_id)
        content_type = accepted_content_type(
            filename, len(data), self._max_bytes, config.allowed_types
        )
        return await self._stores[document_type].upload(
            config.blob_name(filename, applicant_id),
            filename,
            data,
            content_type,
            metadata=config.metadata(applicant_id),
            overwrite=config.overwrite,
        )

    async def list_documents(
        self, document_type: DocumentType, applicant_id: UUID | None
    ) -> list[StoredDocument]:
        config = DOCUMENT_CONFIGS[document_type]
        config.validate_applicant_id(applicant_id)
        return await self._stores[document_type].list_files(prefix=config.folder(applicant_id))
