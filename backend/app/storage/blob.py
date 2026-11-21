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

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient

MAX_FILENAME_CHARS = 100


class StorageError(Exception):
    """Blob Storage couldn't be reached or refused the request."""


class ContainerNotFoundError(StorageError):
    """The container doesn't exist: it is created in the Portal, not by the app."""


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


class BlobStore:
    """One shared client for the app's lifetime (opened at startup, closed at shutdown)."""

    def __init__(
        self,
        service: BlobServiceClient,
        container: str,
        credential: DefaultAzureCredential | None = None,
    ):
        self._service = service
        self._container = service.get_container_client(container)
        self._container_name = container
        self._credential = credential

    @classmethod
    def connect(cls, container: str, account_url: str | None = None) -> "BlobStore":
        """A connection string signs in with the account key (local development). Otherwise the
        account URL signs in with an Entra identity: on Azure, the app's Managed Identity, which
        needs a data role on the account (e.g. Storage Blob Data Contributor)."""
        credential = DefaultAzureCredential()
        return cls(BlobServiceClient(account_url, credential=credential), container, credential)

    async def close(self) -> None:
        await self._service.close()
        if self._credential:
            await self._credential.close()

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
        except ResourceNotFoundError as error:
            raise self._missing_container() from error
        except AzureError as error:
            raise StorageError(str(error)) from error

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
        except ResourceNotFoundError as error:
            raise self._missing_container() from error
        except AzureError as error:
            raise StorageError(str(error)) from error

        return sorted(documents, key=lambda document: document.uploaded_at)

    async def is_reachable(self) -> bool:
        """The account answers and the container exists (for /health)."""
        try:
            return await self._container.exists()
        except AzureError:
            return False

    def _missing_container(self) -> ContainerNotFoundError:
        return ContainerNotFoundError(
            f"Container '{self._container_name}' not found. Check STORAGE_CONTAINER matches the "
            "container you created in the Portal (Storage account → Containers)."
        )
