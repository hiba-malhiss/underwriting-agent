"""What uploaded files are accepted, per kind of document.

The content type comes from the file extension, not from the client, so a renamed file can't
claim to be a PDF.
"""

from pathlib import PurePath

from app.core.errors import BadRequestError

# Applicant documents: what Document Intelligence reads (PDFs and scanned images)
APPLICANT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

# Requirement documents (underwriting guidelines): what the AI Search indexer reads as text
REQUIREMENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


class DocumentRejectedError(BadRequestError):
    """The uploaded file isn't accepted (type, size, or applicant). Answered with 400."""


def accepted_content_type(filename: str, size: int, max_bytes: int, allowed: dict[str, str]) -> str:
    """The content type to store the file with, or DocumentRejectedError."""
    extension = PurePath(filename).suffix.lower()
    if extension not in allowed:
        raise DocumentRejectedError(
            f"Unsupported file type '{extension}'. Allowed: {', '.join(sorted(allowed))}"
        )
    if size == 0:
        raise DocumentRejectedError("The file is empty")
    if size > max_bytes:
        raise DocumentRejectedError(f"The file is larger than {max_bytes // (1024 * 1024)} MB")
    return allowed[extension]
