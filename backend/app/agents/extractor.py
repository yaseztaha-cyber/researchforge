"""Evidence extractor: EXTRACTIVE only — verbatim quotes scored by query overlap.

Never paraphrases into 'evidence'; the quote field must be a substring of the
source content so citations are always traceable.
"""

from __future__ import annotations

import re

from app.schemas.research import EvidenceItem
from app.services.retrieval.base import token_overlap

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])")
_STOP = {"the", "and", "for", "with", "that", "this", "from", "have", "are", "was", "were"}


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT.split(text.strip()) if len(p.strip()) > 30]
    return parts or ([text.strip()] if len(text.strip()) > 30 else [])


def derive_claim(sentence: str) -> str:
    s = sentence.strip()
    return s if len(s) <= 300 else s[:297] + "..."


def extract_evidence(query: str, source_id: str, content: str, *,
                     page: int | None = None, section: str | None = None,
                     top_k: int = 3) -> list[EvidenceItem]:
    out: list[EvidenceItem] = []
    for sent in split_sentences(content):
        rel = round(min(1.0, token_overlap(query, sent) * 3.2 + 0.15), 4)
        if rel < 0.12:
            continue
        conf = round(min(0.95, 0.45 + rel * 0.5 + min(0.1, len(sent) / 3000)), 4)
        out.append(EvidenceItem(claim=derive_claim(sent), quote=sent[:2000], source_id=source_id,
                                page=page, section=section,
                                relevance_score=rel, confidence_score=conf))
    out.sort(key=lambda e: e.relevance_score, reverse=True)
    return out[:top_k]
