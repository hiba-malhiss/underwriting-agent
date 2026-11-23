"""Blob Storage errors: the app's own exceptions, and how Azure SDK errors map onto them.

The SDK raises long, low-level errors; the app raises these instead, each with a short message
that says what to fix. They are AppErrors, so core/error_handlers.py answers them.
"""

from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
)

from app.core.errors import BadGatewayError


class StorageError(BadGatewayError):
    """Blob Storage couldn't be reached or refused the request. Answered with 502, without the
    Azure SDK's details."""

    def public_message(self) -> str:
        return "Storage request failed"


class ContainerNotFoundError(StorageError):
    """The container doesn't exist: it is created in the Portal, not by the app. Answered with
    503 and the message, which says what to fix."""

    status_code = 503

    def public_message(self) -> str:
        return str(self)


class StoredFileNotFoundError(StorageError):
    """The file isn't in the container (already deleted, or a wrong name). Answered with 404."""

    status_code = 404

    def public_message(self) -> str:
        return str(self)


class StorageAuthError(StorageError):
    """The app couldn't sign in to Azure, or its identity has no data role on the account.
    Answered with 503 and the message, which says what to fix."""

    status_code = 503

    def public_message(self) -> str:
        return str(self)


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
    # A missing blob and a missing container are both 404s; the error code tells them apart
    if (
        isinstance(error, ResourceNotFoundError)
        and getattr(error, "error_code", None) == "BlobNotFound"
    ):
        return StoredFileNotFoundError("File not found. It may have been deleted already.")
    if isinstance(error, ResourceNotFoundError):
        return ContainerNotFoundError(
            f"Container '{container}' not found. Create it in the Portal (Storage account → "
            "Containers), or fix the container name in .env."
        )
    return StorageError(str(error))
