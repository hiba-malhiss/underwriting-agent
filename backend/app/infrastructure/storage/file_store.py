"""The file storage contract: what the app needs from any file store.

Features depend on this Protocol, not on Azure: BlobStore implements it today, and the tests use
in-memory fakes. Swapping the storage means a new implementation, not changes in the features
(dependency inversion).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


# frozen: a stored file's details can't be changed after it's created
@dataclass(frozen=True)
class StoredDocument:
    name: str  # where it is stored, e.g. "<applicant_id>/<random>-form.pdf"
    filename: str  # the name the user uploaded
    content_type: str
    size: int
    uploaded_at: datetime


class FileStore(Protocol):
    async def upload(
        self,
        name: str,
        filename: str,
        data: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
        overwrite: bool = False,
    ) -> StoredDocument: ...

    async def list_files(self, prefix: str = "") -> list[StoredDocument]: ...

    async def delete(self, name: str) -> None: ...

    async def is_reachable(self) -> bool: ...

    async def close(self) -> None: ...
