"""Helpers for working with uploaded file names."""

import re
from pathlib import PurePath

MAX_FILENAME_CHARS = 100


def safe_filename(filename: str) -> str:
    """The uploaded name without any path, unsafe characters replaced, cut to a sane length.
    Letters in any language are kept."""
    name = PurePath(filename.replace("\\", "/")).name
    name = re.sub(r"[^\w.\-]", "-", name).strip(".-")
    return name[-MAX_FILENAME_CHARS:] or "document"
