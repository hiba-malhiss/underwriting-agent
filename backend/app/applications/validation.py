"""What application documents are accepted.

The content type comes from the file extension, not from the client, so a renamed file can't
claim to be a PDF.
"""

from pathlib import PurePath

# The formats Document Intelligence reads: PDFs and scanned images
ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


class DocumentRejectedError(ValueError):
    """The uploaded file isn't accepted (type or size)."""


def accepted_content_type(filename: str, size: int, max_bytes: int) -> str:
    """The content type to store the file with, or DocumentRejectedError."""
    extension = PurePath(filename).suffix.lower()
    if extension not in ALLOWED_TYPES:
        allowed = ", ".join(sorted(ALLOWED_TYPES))
        raise DocumentRejectedError(f"Unsupported file type '{extension}'. Allowed: {allowed}")
    if size == 0:
        raise DocumentRejectedError("The file is empty")
    if size > max_bytes:
        raise DocumentRejectedError(f"The file is larger than {max_bytes // (1024 * 1024)} MB")
    return ALLOWED_TYPES[extension]
