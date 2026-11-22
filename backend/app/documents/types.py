"""The kinds of documents the app stores, and everything that differs between them.

- applicant:   what a person submits for their insurance (ID, medical report). Belongs to an
               applicant: stored as `<applicant_id>/<random>-<filename>`, so same-named files
               both stay.
- requirement: the underwriting guidelines. Company-wide: stored by filename, so uploading a
               guideline again replaces the old version.

The service applies these rules for every kind; this table is the only place they differ
(plus their container, in settings). A new kind of document is a new entry here.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid4

from app.core.file_utils import safe_filename
from app.documents.validation import APPLICANT_TYPES, REQUIREMENT_TYPES, DocumentRejectedError


class DocumentType(StrEnum):
    APPLICANT = "applicant"
    REQUIREMENT = "requirement"


@dataclass(frozen=True)
class DocumentTypeConfig:
    allowed_types: dict[str, str]  # extension → content type
    belongs_to_applicant: bool  # belongs to an applicant (needs applicant_id, grouped under it)
    overwrite: bool  # uploading the same file again replaces it

    def validate_applicant_id(self, applicant_id: UUID | None) -> None:
        """applicant_id is required for applicant documents and refused for the others, so a
        mistaken call can't silently file a document in the wrong place."""
        if self.belongs_to_applicant and applicant_id is None:
            raise DocumentRejectedError("applicant_id is required for applicant documents")
        if not self.belongs_to_applicant and applicant_id is not None:
            raise DocumentRejectedError("These documents don't belong to an applicant")

    def folder(self, applicant_id: UUID | None) -> str:
        """The applicant's "folder" (a name prefix: Blob Storage has no real folders), or the
        whole container for documents that don't belong to an applicant."""
        return f"{applicant_id}/" if self.belongs_to_applicant else ""

    def blob_name(self, filename: str, applicant_id: UUID | None) -> str:
        if self.belongs_to_applicant:
            return f"{self.folder(applicant_id)}{uuid4().hex}-{safe_filename(filename)}"
        return safe_filename(filename)

    def metadata(self, applicant_id: UUID | None) -> dict[str, str]:
        return {"applicant_id": str(applicant_id)} if self.belongs_to_applicant else {}


DOCUMENT_CONFIGS: dict[DocumentType, DocumentTypeConfig] = {
    DocumentType.APPLICANT: DocumentTypeConfig(
        APPLICANT_TYPES, belongs_to_applicant=True, overwrite=False
    ),
    DocumentType.REQUIREMENT: DocumentTypeConfig(
        REQUIREMENT_TYPES, belongs_to_applicant=False, overwrite=True
    ),
}
