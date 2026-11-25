"""Document service: the business rules for documents (like a Spring @Service).

Checks who a document belongs to, which formats and sizes are accepted, how it's named and
whether it replaces an older version, then stores it. Lists and deletes documents with the same
ownership rules.

After an upload or delete it asks the search index to catch up (if that kind of document has
one). That's best effort: the file is already safe in storage, so a search failure is logged, not
returned as an error, and the indexer's own schedule picks the change up later.

Plain Python on purpose: no FastAPI (that's the controller and dependencies.py). Its stores and
indexers are passed in, so tests give it fakes, and it can be reused outside HTTP (e.g. a job).
"""

import logging
from uuid import UUID

from app.documents.types import DOCUMENT_CONFIGS, DocumentType
from app.documents.validation import DocumentRejectedError, accepted_content_type
from app.infrastructure.search.exceptions import SearchError
from app.infrastructure.search.indexer import IndexerRunner
from app.infrastructure.storage.blob import BlobStore, StoredDocument

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(
        self,
        stores: dict[DocumentType, BlobStore],
        max_upload_mb: int,
        indexers: dict[DocumentType, IndexerRunner] | None = None,
    ):
        self._stores = stores
        self._max_bytes = max_upload_mb * 1024 * 1024
        self._indexers = indexers or {}

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
        document = await self._stores[document_type].upload(
            config.blob_name(filename, applicant_id),
            filename,
            data,
            content_type,
            metadata=config.metadata(applicant_id),
            overwrite=config.overwrite,
        )
        await self._refresh_index(document_type)
        return document

    async def delete(
        self, document_type: DocumentType, name: str, applicant_id: UUID | None
    ) -> None:
        """Delete one document. `name` is the stored name the list returned. For applicant
        documents it must be in that applicant's folder, so one applicant's page can't delete
        another applicant's files."""
        config = DOCUMENT_CONFIGS[document_type]
        config.validate_applicant_id(applicant_id)
        folder = config.folder(applicant_id)
        if not name.startswith(folder) or name == folder:
            raise DocumentRejectedError("This document doesn't belong to this applicant")
        await self._stores[document_type].delete(name)
        await self._refresh_index(document_type)

    async def list_documents(
        self, document_type: DocumentType, applicant_id: UUID | None
    ) -> list[StoredDocument]:
        config = DOCUMENT_CONFIGS[document_type]
        config.validate_applicant_id(applicant_id)
        return await self._stores[document_type].list_files(prefix=config.folder(applicant_id))

    async def _refresh_index(self, document_type: DocumentType) -> None:
        """Ask the search index to catch up with the container, if this kind has one."""
        indexer = self._indexers.get(document_type)
        if indexer is None:
            return
        try:
            await indexer.run()
        except SearchError as error:
            logger.warning("Couldn't re-index %s documents: %s", document_type, error)
