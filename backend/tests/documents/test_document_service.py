"""The document service alone, with fake stores: business rules without HTTP or Azure."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.documents.service import DocumentService
from app.documents.types import DocumentType
from app.documents.validation import DocumentRejectedError
from app.infrastructure.search.exceptions import SearchError
from app.infrastructure.storage.blob import StoredDocument

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

    async def delete(self, name):
        self.calls.append(("delete", name))


class FakeIndexer:
    """Counts how often the search index was asked to catch up."""

    def __init__(self, error: Exception | None = None):
        self.runs = 0
        self.error = error

    async def run(self):
        self.runs += 1
        if self.error:
            raise self.error


def service_with_fakes(
    indexer: FakeIndexer | None = None,
) -> tuple[DocumentService, dict[DocumentType, FakeStore]]:
    stores = {document_type: FakeStore() for document_type in DocumentType}
    # Only the guidelines have an indexer here, like a setup without APPLICANT_INDEXER
    indexers = {DocumentType.REQUIREMENT: indexer} if indexer else None
    return DocumentService(stores, max_upload_mb=1, indexers=indexers), stores


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


# Delete goes to the right container, by the stored name the list returned
def test_delete_removes_the_document_from_its_container():
    service, stores = service_with_fakes()

    run(service.delete(DocumentType.APPLICANT, f"{APPLICANT_ID}/abc-form.pdf", APPLICANT_ID))
    run(service.delete(DocumentType.REQUIREMENT, "guidelines.pdf", None))

    assert stores[DocumentType.APPLICANT].calls == [("delete", f"{APPLICANT_ID}/abc-form.pdf")]
    assert stores[DocumentType.REQUIREMENT].calls == [("delete", "guidelines.pdf")]


# One applicant's page can't delete another applicant's files (or the folder itself)
@pytest.mark.parametrize(
    "name",
    ["99999999-2222-3333-4444-555555555555/abc-form.pdf", "form.pdf", f"{APPLICANT_ID}/"],
)
def test_delete_refuses_documents_outside_the_applicants_folder(name):
    service, stores = service_with_fakes()

    with pytest.raises(DocumentRejectedError):
        run(service.delete(DocumentType.APPLICANT, name, APPLICANT_ID))
    assert all(store.calls == [] for store in stores.values())


# Uploading or deleting a guideline makes the search index catch up right away
def test_requirement_upload_and_delete_refresh_the_search_index():
    indexer = FakeIndexer()
    service, _ = service_with_fakes(indexer)

    run(service.upload(DocumentType.REQUIREMENT, "guide.pdf", b"%PDF", None))
    run(service.delete(DocumentType.REQUIREMENT, "guide.pdf", None))

    assert indexer.runs == 2


# No indexer for that kind (or a rejected file): nothing to re-index
def test_no_reindex_without_an_indexer_or_after_a_rejected_upload():
    indexer = FakeIndexer()
    service, _ = service_with_fakes(indexer)

    run(service.upload(DocumentType.APPLICANT, "form.pdf", b"%PDF", APPLICANT_ID))
    with pytest.raises(DocumentRejectedError):
        run(service.upload(DocumentType.REQUIREMENT, "scan.png", b"x", None))

    assert indexer.runs == 0


# The file is already stored: a search failure is logged, the upload still succeeds
def test_a_search_failure_does_not_fail_the_upload():
    service, stores = service_with_fakes(FakeIndexer(error=SearchError("search down")))

    document = run(service.upload(DocumentType.REQUIREMENT, "guide.pdf", b"%PDF", None))

    assert document.name == "guide.pdf"
    assert stores[DocumentType.REQUIREMENT].calls == [("upload", "guide.pdf", True)]
