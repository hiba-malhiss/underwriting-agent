"""The document service alone, with fake stores: business rules without HTTP or Azure."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.documents.service import DocumentService
from app.documents.types import DocumentType
from app.documents.validation import DocumentRejectedError
from app.infrastructure.storage.file_store import StoredDocument

APPLICANT_ID = UUID("11111111-2222-3333-4444-555555555555")


class FakeStore:
    """Records what the service asked the store to do."""

    def __init__(self):
        self.calls: list[tuple] = []

    async def upload(self, name, filename, data, content_type, metadata=None, overwrite=False):
        self.calls.append(("upload", name, overwrite))
        return StoredDocument(name, filename, content_type, len(data), datetime.now(UTC))

    async def list_files(self, prefix=""):
        self.calls.append(("list_files", prefix))
        return []


def service_with_fakes() -> tuple[DocumentService, dict[DocumentType, FakeStore]]:
    stores = {document_type: FakeStore() for document_type in DocumentType}
    return DocumentService(stores, max_upload_mb=1), stores


def run(coroutine):
    return asyncio.run(coroutine)


# Listing reads the right container, and only the applicant's folder for applicant documents
def test_list_reads_the_applicants_folder_or_the_whole_container():
    service, stores = service_with_fakes()

    run(service.list_documents(DocumentType.APPLICANT, APPLICANT_ID))
    run(service.list_documents(DocumentType.REQUIREMENT, None))

    assert stores[DocumentType.APPLICANT].calls == [("list_files", f"{APPLICANT_ID}/")]
    assert stores[DocumentType.REQUIREMENT].calls == [("list_files", "")]


# The rules run before storage: a rejected file never reaches a store
@pytest.mark.parametrize(
    ("document_type", "filename", "size", "applicant_id"),
    [
        (DocumentType.APPLICANT, "form.pdf", 10, None),  # missing applicant
        (DocumentType.REQUIREMENT, "scan.png", 10, None),  # wrong format for guidelines
        (DocumentType.APPLICANT, "form.pdf", 2 * 1024 * 1024, APPLICANT_ID),  # over 1 MB
    ],
)
def test_rejected_upload_never_reaches_storage(document_type, filename, size, applicant_id):
    service, stores = service_with_fakes()

    with pytest.raises(DocumentRejectedError):
        run(service.upload(document_type, filename, b"x" * size, applicant_id))
    assert all(store.calls == [] for store in stores.values())
