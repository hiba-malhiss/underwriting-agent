"""Document naming and acceptance rules (no Azure calls)."""

from uuid import UUID

import pytest

from app.documents.types import DOCUMENT_CONFIGS, DocumentType
from app.documents.validation import (
    APPLICANT_TYPES,
    REQUIREMENT_TYPES,
    DocumentRejectedError,
    accepted_content_type,
)

APPLICANT_ID = UUID("11111111-2222-3333-4444-555555555555")
MB = 1024 * 1024


# Applicant documents are grouped under the applicant, and two uploads never share a name
def test_blob_name_is_under_the_applicant_and_unique():
    applicant = DOCUMENT_CONFIGS[DocumentType.APPLICANT]
    first = applicant.blob_name("form.pdf", APPLICANT_ID)
    second = applicant.blob_name("form.pdf", APPLICANT_ID)
    assert first.startswith(f"{APPLICANT_ID}/") and first.endswith("-form.pdf")
    assert first != second


# The content type comes from the extension, not from the client
def test_accepts_pdf_and_images():
    assert accepted_content_type("form.PDF", 10, MB, APPLICANT_TYPES) == "application/pdf"
    assert accepted_content_type("scan.jpg", 10, MB, APPLICANT_TYPES) == "image/jpeg"


@pytest.mark.parametrize(
    ("filename", "size"),
    [("virus.exe", 10), ("form.pdf", 0), ("form.pdf", 2 * MB)],
)
def test_rejects_wrong_type_empty_or_too_large(filename, size):
    with pytest.raises(DocumentRejectedError):
        accepted_content_type(filename, size, MB, APPLICANT_TYPES)


# Each kind of document has its own formats: guidelines can be Word or text, not images
def test_requirement_types_accept_text_formats_not_images():
    assert accepted_content_type("guide.docx", 10, MB, REQUIREMENT_TYPES).endswith("document")
    assert accepted_content_type("guide.md", 10, MB, REQUIREMENT_TYPES) == "text/markdown"
    with pytest.raises(DocumentRejectedError):
        accepted_content_type("scan.png", 10, MB, REQUIREMENT_TYPES)
