"""Reads documents (PDFs, scans) into text with Azure Document Intelligence (Layout model).

The text comes back as ONE continuous string in reading order, not page by page, so a paragraph
that starts at the bottom of one page and ends on the next stays whole. Where each page starts
and ends inside that string is kept too, so any quote can be traced back to its page (or pages).

The identity needs the 'Cognitive Services User' role on the resource. Document Intelligence runs
on the Foundry (AI Services) resource, so its endpoint is the same.
"""

import re
from dataclasses import dataclass

from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError, HttpResponseError

from app.core.errors import BadGatewayError

# How Layout writes the checkboxes it sees, and how we show them: a ticked box matters (e.g.
# "Do you smoke? [x] Yes [ ] No"), so it's kept in a form the LLM reads easily
_CHECKBOX_MARKS = {":selected:": "[x]", ":unselected:": "[ ]"}
_CHECKBOX_SHOWN = set(_CHECKBOX_MARKS.values())

# Quote matching reads the text as tokens: a checkbox mark, a bullet symbol standing alone
# (spaces or a line edge on both sides), a run of spaces, or any other single character
_BULLET_CHARS = r"[.•·●▪‣◦*\-–—]"
_TOKEN = re.compile(rf"\[x\]|\[ \]|(?<!\S){_BULLET_CHARS}(?!\S)|\s+|\S")
_BULLET = re.compile(_BULLET_CHARS)

# Typographic characters normalised for quote matching: the LLM often writes plain ASCII
_SAME_CHARACTER = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


@dataclass(frozen=True)
class PageSpan:
    number: int  # 1-based, as printed
    start: int  # offset of the page's first character in DocumentText.content
    end: int  # offset just after its last character


@dataclass(frozen=True)
class DocumentText:
    content: str
    pages: list[PageSpan]

    def page_at(self, offset: int) -> int | None:
        for page in self.pages:
            if page.start <= offset < page.end:
                return page.number
        return None

    def with_page_markers(self) -> str:
        """The text with a "[page N]" line where each page starts: what the LLM reads, so it
        reads across page breaks but can still tell which page it's on."""
        parts, position = [], 0
        for page in self.pages:
            parts.append(self.content[position : page.start])
            parts.append(f"\n[page {page.number}]\n")
            position = page.start
        parts.append(self.content[position:])
        return "".join(parts).lstrip("\n")

    def locate(self, quote: str) -> tuple[int, int] | None:
        """The first and last page of `quote` in the text, or None if it isn't there.

        Line breaks, extra spaces, curly quotes, checkbox marks and punctuation at the quote's
        edges don't count, so a quote that runs across a page break (and therefore a line break)
        still matches, but its words must be exactly in the text."""
        text, offsets = _squeeze(self.content)
        target, _ = _squeeze(quote)
        # Punctuation at the edges doesn't count: the LLM may end a part of a sentence with "."
        target = target.strip(" .,;:")
        if not target:
            return None
        found = text.find(target)
        if found == -1:
            return None
        first = self.page_at(offsets[found])
        last = self.page_at(offsets[found + len(target) - 1])
        if first is None or last is None:
            return None
        return first, last


def _squeeze(text: str) -> tuple[str, list[int]]:
    """`text` with every run of whitespace turned into one space (and curly quotes / dashes made
    plain), plus, for each kept character, its offset in the original text.

    Checkbox marks ("[x]", "[ ]") and bullet symbols standing alone (". " at a line start, "•",
    "·", "-") count as spaces: Layout reads bullet points as ticked boxes or as a stray ".", so
    they can sit between two bullets the LLM quotes together. A dot inside a number (7.5) or at a
    sentence's end isn't alone, so it still counts."""
    kept: list[str] = []
    offsets: list[int] = []
    for match in _TOKEN.finditer(text.translate(_SAME_CHARACTER)):
        piece = match.group(0)
        if piece.isspace() or piece in _CHECKBOX_SHOWN or _BULLET.fullmatch(piece):
            if kept and kept[-1] != " ":
                kept.append(" ")
                offsets.append(match.start())
        else:
            kept.append(piece)
            offsets.append(match.start())
    if kept and kept[-1] == " ":
        kept.pop()
        offsets.pop()
    return "".join(kept), offsets


class DocumentReadError(BadGatewayError):
    """Document Intelligence couldn't read the file. Answered with 502, or with a message that
    says what to fix."""

    def public_message(self) -> str:
        return str(self)


class DocumentReader:
    """One shared client for the app's lifetime (opened at startup, closed at shutdown)."""

    def __init__(self, client: DocumentIntelligenceClient):
        self._client = client

    @classmethod
    def connect(cls, endpoint: str, credential: AsyncTokenCredential) -> "DocumentReader":
        return cls(DocumentIntelligenceClient(endpoint, credential))

    async def read(self, data: bytes) -> DocumentText:
        try:
            poller = await self._client.begin_analyze_document(
                "prebuilt-layout",
                AnalyzeDocumentRequest(bytes_source=data),
                # Count characters like Python does, so page offsets match the string
                string_index_type="unicodeCodePoint",
            )
            result = await poller.result()
        except HttpResponseError as error:
            if error.status_code in (401, 403):
                raise DocumentReadError(
                    "Not allowed to use Document Intelligence. Give your identity the "
                    "'Cognitive Services User' role on the AI resource (Access control (IAM))."
                ) from error
            raise DocumentReadError(f"Couldn't read the document: {error.message}") from error
        except AzureError as error:
            raise DocumentReadError("Document Intelligence couldn't be reached") from error

        pages = [
            PageSpan(
                number=page.page_number,
                start=page.spans[0].offset,
                end=page.spans[-1].offset + page.spans[-1].length,
            )
            for page in result.pages or []
            if page.spans
        ]
        return DocumentText(content=_readable_checkboxes(result.content or ""), pages=pages)

    async def close(self) -> None:
        await self._client.close()


def _readable_checkboxes(content: str) -> str:
    """ ":selected:" → "[x]" and ":unselected:" → "[ ]", padded with spaces to the same length,
    so every page's offsets stay correct."""
    for mark, shown in _CHECKBOX_MARKS.items():
        # ljust() بتضيف مسافات على يمين النص حتى يصير بنفس الطول الأصلي.
        # مثلاً:
        #   ":selected:"  # 10 characters
        #   "[x]"         # 3 characters → "[x]" + 7 spaces = 10 characters
        content = content.replace(mark, shown.ljust(len(mark)))
    return content
