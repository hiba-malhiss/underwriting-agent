"""Azure Blob Storage access: store a file under a name, list files under a prefix, delete one.

One BlobStore per container. The callers decide the names; the naming rules and accepted
formats per kind of document live in documents/.

This module only stores, lists and deletes. It knows nothing about HTTP or what files are accepted.
"""

from urllib.parse import quote, unquote

from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient

from app.infrastructure.storage.exceptions import to_storage_error
from app.infrastructure.storage.file_store import FileStore, StoredDocument


class BlobStore(FileStore):
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
        self,
        name: str,
        filename: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
        overwrite: bool = False,
    ) -> StoredDocument:
        """Store `data` as the blob `name`. `filename` is the name the user uploaded, kept in the
        blob's metadata (quoted: metadata travels as HTTP headers, which must be ASCII)."""
        try:
            blob_client = self._container.get_blob_client(name)
            await blob_client.upload_blob(
                data,
                content_settings=ContentSettings(content_type=content_type),
                metadata={**(metadata or {}), "filename": quote(filename)},
                overwrite=overwrite,
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

    async def list_files(self, prefix: str = "") -> list[StoredDocument]:
        """The blobs whose name starts with `prefix` (all of them by default), oldest first."""
        documents = []
        try:
            async for blob in self._container.list_blobs(
                name_starts_with=prefix or None, include=["metadata"]
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

    async def delete(self, name: str) -> None:
        """Delete the blob `name` (and its snapshots). With soft delete on in the storage account,
        Azure keeps it recoverable for the retention period."""
        try:
            await self._container.get_blob_client(name).delete_blob(delete_snapshots="include")
        except AzureError as error:
            raise to_storage_error(error, self._container_name) from error

    async def is_reachable(self) -> bool:
        """The account answers and the container exists (for /health)."""
        try:
            return await self._container.exists()
        except AzureError:
            return False
