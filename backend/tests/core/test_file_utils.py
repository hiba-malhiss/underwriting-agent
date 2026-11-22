"""safe_filename: turning an uploaded name into a safe storage name."""

from app.core.file_utils import safe_filename


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
