"""Document naming and acceptance rules (no Azure calls)."""

from uuid import UUID

import pytest

from app.applications.validation import DocumentRejectedError, accepted_content_type
from app.storage.blob import blob_name, safe_filename

APP_ID = UUID("11111111-2222-3333-4444-555555555555")
MB = 1024 * 1024


# A path in the uploaded name must not leak into the blob name
def test_safe_filename_drops_paths():
    assert safe_filename("../../etc/form.pdf") == "form.pdf"
    assert safe_filename("C:\\Users\\sara\\form.pdf") == "form.pdf"


# Unsafe characters are replaced; letters in any language are kept
def test_safe_filename_replaces_unsafe_characters_keeps_letters():
    assert safe_filename("medical report?.pdf") == "medical-report-.pdf"
    assert safe_filename("تقرير.pdf") == "تقرير.pdf"


def test_safe_filename_never_empty():
    assert safe_filename("...") == "document"


# Documents are grouped under their application, and two uploads never share a name
def test_blob_name_is_under_the_application_and_unique():
    first = blob_name(APP_ID, "form.pdf")
    second = blob_name(APP_ID, "form.pdf")
    assert first.startswith(f"{APP_ID}/") and first.endswith("-form.pdf")
    assert first != second


# The content type comes from the extension, not from the client
def test_accepts_pdf_and_images():
    assert accepted_content_type("form.PDF", 10, MB) == "application/pdf"
    assert accepted_content_type("scan.jpg", 10, MB) == "image/jpeg"


@pytest.mark.parametrize(
    ("filename", "size"),
    [("virus.exe", 10), ("form.pdf", 0), ("form.pdf", 2 * MB)],
)
def test_rejects_wrong_type_empty_or_too_large(filename, size):
    with pytest.raises(DocumentRejectedError):
        accepted_content_type(filename, size, MB)
