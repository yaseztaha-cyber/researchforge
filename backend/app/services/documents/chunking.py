"""Structure-aware chunking service for v0.3.

Priority:
1. markdown headings
2. paragraphs (blank-line delimited)
3. sentence boundaries
4. fixed-size word-window fallback

Preserves: document_id, chunk_index, page, section, heading, char offsets,
content_hash. Never splits blindly every N characters without consulting
structure first.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“])")
_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_PARA_SPLIT = re.compile(r"\n\s*\n")

_WORD_RE = re.compile(r"\S+")


@dataclass
class ChunkV3:
    index: int
    text: str
    page: int | None
    section: str | None
    heading: str | None
    char_start: int
    char_end: int
    content_hash: str


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def normalize_text(text: str) -> str:
    """Light normalization: collapse excessive whitespace, preserve paragraphs/headings."""
    # Normalize line endings, collapse >2 blank lines to 2
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse horizontal whitespace but keep single newlines
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def chunk_document_v3(
    text: str,
    *,
    target_words: int = 700,
    overlap_words: int = 80,
    pages: list[str] | None = None,
) -> list[ChunkV3]:
    """Structure-aware chunking: heading -> paragraph -> sentence -> fixed window."""
    text = normalize_text(text)
    if not text:
        return []

    # Collect headings with offsets and page inference
    headings: list[tuple[int, str]] = [(m.start(), m.group(2).strip()) for m in _HEADING.finditer(text)]
    # Map char offset -> heading
    def _heading_for(offset: int) -> str | None:
        cur = None
        for pos, title in headings:
            if pos <= offset:
                cur = title
            else:
                break
        return cur

    # If pages provided (PDF), respect page boundaries as hard splits first
    sections: list[tuple[str, int | None]] = []
    if pages:
        offset = 0
        for idx, page_text in enumerate(pages):
            page_norm = normalize_text(page_text)
            if page_norm:
                sections.append((page_norm, idx + 1))
            offset += len(page_norm) + 2
    else:
        # Split by headings first, then paragraphs within each heading block
        if headings:
            # Slice text at heading boundaries
            bounds = [pos for pos, _ in headings] + [len(text)]
            for i in range(len(headings)):
                block = text[bounds[i] : bounds[i + 1]].strip()
                if block:
                    sections.append((block, None))
            # Leading text before first heading
            if headings[0][0] > 0:
                lead = text[: headings[0][0]].strip()
                if lead:
                    sections.insert(0, (lead, None))
        else:
            sections.append((text, None))

    chunks: list[ChunkV3] = []
    global_offset = 0
    idx = 0

    for section_text, page in sections:
        # Within each section, split into paragraphs
        paras = [p.strip() for p in _PARA_SPLIT.split(section_text) if p.strip()]
        if not paras:
            continue
        # Build word-window chunks but prefer not to split mid-paragraph unless needed
        words: list[str] = []
        para_boundaries: set[int] = set()
        for para in paras:
            start = len(words)
            words.extend(para.split())
            para_boundaries.add(len(words))

        i = 0
        while i < len(words):
            end = min(len(words), i + target_words)
            # Prefer to end at paragraph boundary if within overlap slack
            if end < len(words):
                # Look back up to overlap_words for nearest paragraph boundary
                for b in sorted(para_boundaries, reverse=True):
                    if i < b <= end and (end - b) <= overlap_words:
                        end = b
                        break
                # Otherwise prefer sentence boundary
                if end == i + target_words:
                    # Find sentence-like break within last overlap_words
                    window_text = " ".join(words[i:end])
                    sents = _SENT.split(window_text)
                    if len(sents) > 1 and len(sents[-1].split()) <= overlap_words:
                        end = end - len(sents[-1].split())
            chunk_words = words[i:end]
            chunk_text = " ".join(chunk_words)
            if not chunk_text:
                i = end
                continue
            # Char offsets relative to original normalized text (approx via search)
            try:
                char_start = text.index(chunk_text[: min(40, len(chunk_text))], global_offset) if global_offset < len(text) else global_offset
            except ValueError:
                char_start = global_offset
            char_end = char_start + len(chunk_text)
            heading = _heading_for(char_start)
            # Section is heading without markdown markers; fallback to keyword heuristic
            section = heading
            if page is None and section is None:
                low = chunk_text.lower()
                for key in ("energy", "brine", "marine", "mitigat", "method", "result", "conclusion"):
                    if key in low[:800]:
                        section = key.capitalize()
                        break
            chunks.append(ChunkV3(index=idx, text=chunk_text, page=page, section=section, heading=heading,
                                  char_start=char_start, char_end=char_end, content_hash=_content_hash(chunk_text)))
            idx += 1
            if end >= len(words):
                break
            i = max(end - overlap_words, i + 1)
        # Advance global offset roughly
        global_offset += len(section_text) + 2

    # Fallback: if chunking produced nothing but text exists, single chunk
    if not chunks and text:
        chunks.append(ChunkV3(index=0, text=text[: target_words * 6], page=None, section=None, heading=None,
                              char_start=0, char_end=len(text), content_hash=_content_hash(text)))
    return chunks
