"""Azure Blob Storage access for application documents.

Each document is one blob in the private container, named `<application_id>/<random>-<filename>`.
The prefix groups an application's documents (Blob Storage has no real folders, only names with
"/"), and the random part keeps two uploads with the same filename from overwriting each other.

This module only stores and lists. It knows nothing about HTTP or what files are accepted:
that's the service's job.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePath
from urllib.parse import quote, unquote
from uuid import UUID, uuid4

from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
)
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient

MAX_FILENAME_CHARS = 100


class StorageError(Exception):
    """Blob Storage couldn't be reached or refused the request."""


class ContainerNotFoundError(StorageError):
    """The container doesn't exist: it is created in the Portal, not by the app."""


class StorageAuthError(StorageError):
    """The app couldn't sign in to Azure, or its identity has no data role on the account."""


# prepare constructure disable update obj after creation
@dataclass(frozen=True)
class StoredDocument:
    name: str
    filename: str
    content_type: str
    size: int
    uploaded_at: datetime


def safe_filename(filename: str) -> str:
    """The uploaded name without any path, unsafe characters replaced, spaces"""
    name = PurePath(filename.replace("\\", "/")).name
    name = re.sub(r"[^\w.\-]", "-", name).strip(".-")
    return name[-MAX_FILENAME_CHARS:] or "document"


def blob_name(application_id: UUID, filename: str) -> str:
    """Where a new document of this application is stored."""
    return f"{application_id}/{uuid4().hex}-{safe_filename(filename)}"


def to_storage_error(error: AzureError, container: str) -> StorageError:
    """A short, actionable error instead of the Azure SDK's full report."""
    if isinstance(error, ClientAuthenticationError):
        return StorageAuthError(
            "Couldn't sign in to Azure. Locally, set AZURE_INTERACTIVE_LOGIN=true and "
            "AZURE_TENANT_ID in .env; on Azure, enable the app's Managed Identity."
        )
    if isinstance(error, HttpResponseError) and error.status_code == 403:
        return StorageAuthError(
            "Signed in, but not allowed to use the blobs. Give your identity the "
            "'Storage Blob Data Contributor' role on the storage account (Access control "
            "(IAM)). Owner isn't enough: it manages the account, not its data."
        )
    if isinstance(error, ResourceNotFoundError):
        return ContainerNotFoundError(
            f"Container '{container}' not found. Check STORAGE_CONTAINER matches "
            "the container you created in the Portal (Storage account → Containers)."
        )
    return StorageError(str(error))


class BlobStore:
    """One shared client for the app's lifetime (opened at startup, closed at shutdown)."""

    def __init__(self, service: BlobServiceClient, container: str):
        self._service = service
        self._container = service.get_container_client(container)
        self._container_name = container

    @classmethod
    def connect(
        cls, account_url: str, container: str, credential: AsyncTokenCredential
    ) -> "BlobStore":
        """Sign in to the account with an Entra identity (see core/azure_credential.py). The
        identity needs a DATA role on the account, e.g. Storage Blob Data Contributor: Owner or
        Contributor only manage the account, they don't read or write its blobs."""
        return cls(BlobServiceClient(account_url, credential=credential), container)

    async def close(self) -> None:
        await self._service.close()

    async def upload(
        self, application_id: UUID, filename: str, data: bytes, content_type: str
    ) -> StoredDocument:
        name = blob_name(application_id, filename)
        try:
            blob_client = self._container.get_blob_client(name)

            await blob_client.upload_blob(
                data,
                content_settings=ContentSettings(content_type=content_type),
                metadata={"application_id": str(application_id), "filename": quote(filename)},
                overwrite=False,
            )

            properties = await blob_client.get_blob_properties()
        except AzureError as error:
            raise to_storage_error(error, self._container_name) from error

        return StoredDocument(
            name=name,
            filename=filename,
            content_type=content_type,
            size=properties.size,
            uploaded_at=properties.last_modified,
        )

    async def list_documents(self, application_id: UUID) -> list[StoredDocument]:
        documents = []
        try:
            async for blob in self._container.list_blobs(
                name_starts_with=f"{application_id}/", include=["metadata"]
            ):
                metadata = blob.metadata or {}
                documents.append(
                    StoredDocument(
                        name=blob.name,
                        filename=unquote(metadata.get("filename", blob.name)),
                        content_type=blob.content_settings.content_type or "",
                        size=blob.size,
                        uploaded_at=blob.last_modified,
                    )
                )
        except AzureError as error:
            raise to_storage_error(error, self._container_name) from error

        return sorted(documents, key=lambda document: document.uploaded_at)

    async def is_reachable(self) -> bool:
        """The account answers and the container exists (for /health)."""
        try:
            return await self._container.exists()
        except AzureError:
            return False
