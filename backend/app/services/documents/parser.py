"""Document parsing (PDF/TXT/MD) + chunking with page/section metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedDoc:
    text: str
    pages: list[str]
    sections: list[str]


def parse_txt(raw: bytes) -> ParsedDoc:
    text = raw.decode("utf-8", errors="replace")
    return ParsedDoc(text=text, pages=[text], sections=[])


def parse_pdf(raw: bytes) -> ParsedDoc:
    from pypdf import PdfReader
    import io

    reader = PdfReader(io.BytesIO(raw))
    pages: list[str] = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    return ParsedDoc(text="\n\n".join(pages), pages=pages, sections=[])


def parse_document(filename: str, raw: bytes) -> ParsedDoc:
    name = filename.lower()
    if name.endswith(".pdf"):
        try:
            return parse_pdf(raw)
        except Exception as e:
            raise ValueError(f"PDF parsing failed: {e}") from e
    if name.endswith((".txt", ".md", ".markdown")):
        return parse_txt(raw)
    raise ValueError(f"Unsupported file format for {filename!r}")


@dataclass
class Chunk:
    index: int
    text: str
    page: int | None
    section: str | None


_HEADING = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


def chunk_text(text: str, *, target: int = 900, overlap: int = 120) -> list[Chunk]:
    """Word-window chunking that propagates the latest markdown heading as section."""
    headings = [(m.start(), m.group(1).strip()) for m in _HEADING.finditer(text)]
    words = text.split()
    chunks: list[Chunk] = []
    i, idx = 0, 0
    while i < len(words):
        window = words[i : i + target]
        ctext = " ".join(window)
        # approximate char offset -> heading lookup
        offset = len(" ".join(words[:i]))
        section = None
        for pos, title in headings:
            if pos <= offset:
                section = title
            else:
                break
        chunks.append(Chunk(index=idx, text=ctext, page=None, section=section))
        idx += 1
        i += max(1, target - overlap)
        if i >= len(words):
            break
    return chunks or [Chunk(index=0, text=text[:target], page=None, section=None)]
