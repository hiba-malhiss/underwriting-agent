"""The /documents API through its layers (controller → service → store), with fake
stores instead of Azure: how each kind is named and stored."""

import os
from datetime import UTC, datetime

# Settings need a storage URL at import; nothing connects to it in these tests
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_URL", "https://example.blob.core.windows.net")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.documents.dependencies import get_indexers, get_stores  # noqa: E402
from app.documents.types import DocumentType  # noqa: E402
from app.infrastructure.storage.blob import StoredDocument  # noqa: E402
from app.infrastructure.storage.exceptions import (  # noqa: E402
    ContainerNotFoundError,
    StorageError,
    StoredFileNotFoundError,
)
from app.main import app  # noqa: E402

APPLICANT_ID = "11111111-2222-3333-4444-555555555555"
PDF = {"file": ("form.pdf", b"%PDF", "x/ignored")}


class FakeStore:
    """Records uploads in memory, like a container."""

    def __init__(self):
        self.uploads: list[dict] = []
        self.deleted: list[str] = []

    async def upload(self, name, filename, data, content_type, metadata=None, overwrite=False):
        self.uploads.append({"name": name, "overwrite": overwrite, "metadata": metadata})
        return StoredDocument(name, filename, content_type, len(data), datetime.now(UTC))

    async def list_files(self, prefix=""):
        return []

    async def delete(self, name):
        self.deleted.append(name)


@pytest.fixture
def stores():
    fakes = {document_type: FakeStore() for document_type in DocumentType}
    app.dependency_overrides = {get_stores: lambda: fakes, get_indexers: lambda: {}}
    yield fakes
    app.dependency_overrides = {}


@pytest.fixture
def client():
    # No `with`: the app's startup (which connects to Azure) doesn't run
    return TestClient(app)


# Applicant documents: under the applicant, with a random part so same-named files both stay
def test_applicant_document_is_stored_under_the_applicant(stores, client):
    response = client.post(f"/documents?type=applicant&applicant_id={APPLICANT_ID}", files=PDF)
    assert response.status_code == 201
    upload = stores[DocumentType.APPLICANT].uploads[0]
    assert upload["name"].startswith(f"{APPLICANT_ID}/") and upload["name"].endswith("-form.pdf")
    assert upload["overwrite"] is False
    assert upload["metadata"] == {"applicant_id": APPLICANT_ID}
    assert response.json()["content_type"] == "application/pdf"  # from the extension
    assert stores[DocumentType.REQUIREMENT].uploads == []  # went to the right container


# Guidelines: named by the file itself, and replaced when uploaded again
def test_requirement_is_named_by_its_file_and_replaces_the_old_version(stores, client):
    files = {"file": ("health guidelines.pdf", b"%PDF", "x")}
    response = client.post("/documents?type=requirement", files=files)
    assert response.status_code == 201
    upload = stores[DocumentType.REQUIREMENT].uploads[0]
    assert upload == {"name": "health-guidelines.pdf", "overwrite": True, "metadata": {}}


# applicant_id is required for applicant documents and refused for guidelines, so a mistaken
# call can't file a document in the wrong place
@pytest.mark.parametrize(
    "query",
    ["type=applicant", f"type=requirement&applicant_id={APPLICANT_ID}"],
)
def test_applicant_id_must_match_the_document_type(stores, client, query):
    response = client.post(f"/documents?{query}", files=PDF)
    assert response.status_code == 400
    assert all(store.uploads == [] for store in stores.values())


def test_unknown_type_is_rejected(stores, client):
    assert client.post("/documents?type=contract", files=PDF).status_code == 422


def test_requirement_upload_rejects_images(stores, client):
    files = {"file": ("scan.png", b"x", "image/png")}
    assert client.post("/documents?type=requirement", files=files).status_code == 400


class BrokenStore(FakeStore):
    def __init__(self, error):
        super().__init__()
        self.error = error

    async def list_files(self, prefix=""):
        raise self.error


# The global error handlers: setup problems say what to fix (503); other storage failures don't
# leak the Azure SDK's details (502)
@pytest.mark.parametrize(
    ("error", "code", "detail"),
    [
        (ContainerNotFoundError("Container 'requirements' not found"), 503, "Container"),
        (StorageError("raw SDK message with internals"), 502, "Storage request failed"),
    ],
)
def test_storage_errors_become_clear_responses(client, error, code, detail):
    app.dependency_overrides = {
        get_indexers: lambda: {},
        get_stores: lambda: {document_type: BrokenStore(error) for document_type in DocumentType},
    }
    response = client.get("/documents?type=requirement")
    app.dependency_overrides = {}
    assert response.status_code == code
    assert response.json()["detail"].startswith(detail)


# DELETE answers 204 and removes the document from the right container
def test_delete_removes_the_document(stores, client):
    name = f"{APPLICANT_ID}/abc-form.pdf"
    response = client.delete(
        "/documents", params={"type": "applicant", "applicant_id": APPLICANT_ID, "name": name}
    )
    assert response.status_code == 204
    assert stores[DocumentType.APPLICANT].deleted == [name]
    assert stores[DocumentType.REQUIREMENT].deleted == []


class MissingBlobStore(FakeStore):
    async def delete(self, name):
        raise StoredFileNotFoundError("File not found. It may have been deleted already.")


# Deleting a file that's already gone is a clear 404, not a storage failure
def test_delete_of_a_missing_file_is_404(client):
    app.dependency_overrides = {
        get_indexers: lambda: {},
        get_stores: lambda: {document_type: MissingBlobStore() for document_type in DocumentType},
    }
    response = client.delete("/documents", params={"type": "requirement", "name": "gone.pdf"})
    app.dependency_overrides = {}
    assert response.status_code == 404
    assert response.json()["detail"].startswith("File not found")
