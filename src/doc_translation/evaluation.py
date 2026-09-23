"""Offline metrics for completed DOCX outputs."""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from pydantic import BaseModel, ConfigDict, Field

from doc_translation.domain.critical_validation import CriticalToken

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NUMERIC_TOKEN = re.compile(r"(?<!\w)[<>≤≥]?\d+(?:[.,]\d+)?(?:[/-]\d+)*(?!\w)")


class ReviewedRegion(BaseModel):
    """One manually reviewed source region used as an evaluation anchor."""

    model_config = ConfigDict(extra="forbid")

    region_id: str
    expected_text: str = Field(min_length=1)


class ReviewedAnchors(BaseModel):
    """Versioned, network-independent reviewed anchors for one document."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    regions: list[ReviewedRegion] = Field(min_length=1)


def content_retention(path: Path, anchors: ReviewedAnchors) -> float:
    """Return the fraction of anchored regions represented by nonempty editable text."""

    with ZipFile(path) as package:
        root = ElementTree.fromstring(package.read("word/document.xml"))
    text_present = any((node.text or "").strip() for node in root.findall(f".//{WORD}t"))
    bookmark_names = {
        node.get(f"{WORD}name")
        for node in root.findall(f".//{WORD}bookmarkStart")
    }
    represented = sum(
        text_present and region.region_id.replace("-", "_") in bookmark_names
        for region in anchors.regions
    )
    return represented / len(anchors.regions)


def _bookmarked_text(path: Path) -> dict[str, str]:
    with ZipFile(path) as package:
        root = ElementTree.fromstring(package.read("word/document.xml"))

    text_by_bookmark: dict[str, list[str]] = {}
    active: list[str] = []
    for node in root.iter():
        if node.tag == f"{WORD}bookmarkStart":
            name = node.get(f"{WORD}name")
            if name:
                active.append(name)
                text_by_bookmark.setdefault(name, [])
        elif node.tag == f"{WORD}t" and active:
            for name in active:
                text_by_bookmark[name].append(node.text or "")
        elif node.tag == f"{WORD}bookmarkEnd":
            bookmark_id = node.get(f"{WORD}id")
            starts = root.findall(f".//{WORD}bookmarkStart")
            for start in reversed(starts):
                if start.get(f"{WORD}id") == bookmark_id:
                    name = start.get(f"{WORD}name")
                    if name in active:
                        active.remove(name)
                    break
    return {name: "".join(parts) for name, parts in text_by_bookmark.items()}


def critical_token_recall(path: Path, tokens: list[CriticalToken]) -> float:
    """Return the fraction of expected critical tokens preserved in their region."""

    if not tokens:
        return 1.0
    text_by_bookmark = _bookmarked_text(path)
    matched = 0
    for token in tokens:
        text = text_by_bookmark.get(token.region_id.replace("-", "_"), "")
        if token.value not in text:
            continue
        if token.unit is not None and token.unit not in text:
            continue
        if token.operator is not None and token.operator not in text:
            continue
        matched += 1
    return matched / len(tokens)


def critical_token_precision(path: Path, tokens: list[CriticalToken]) -> float:
    """Return the fraction of numeric-like output tokens in the reviewed inventory."""

    text_by_bookmark = _bookmarked_text(path)
    observed = {
        (name, value)
        for name, text in text_by_bookmark.items()
        for value in NUMERIC_TOKEN.findall(text)
    }
    expected = {
        (token.region_id.replace("-", "_"), token.value)
        for token in tokens
        if token.kind in {"number", "date"}
    }
    if not observed:
        return 1.0 if not expected else 0.0
    return len(observed & expected) / len(observed)
