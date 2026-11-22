from datetime import datetime
from typing import Self

from pydantic import BaseModel

from app.infrastructure.storage.file_store import StoredDocument


class DocumentResponse(BaseModel):
    name: str
    filename: str
    content_type: str
    size: int
    uploaded_at: datetime

    @classmethod
    def from_stored(cls, document: StoredDocument) -> Self:
        return cls(
            name=document.name,
            filename=document.filename,
            content_type=document.content_type,
            size=document.size,
            uploaded_at=document.uploaded_at,
        )


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
