"""Offline metrics for completed DOCX outputs."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from xml.etree import ElementTree
from zipfile import ZipFile

from pydantic import BaseModel, ConfigDict, Field

from doc_translation.adapters.docx_validation import (
    find_libreoffice,
    inspect_docx,
    roundtrip_docx,
)
from doc_translation.domain.critical_validation import CriticalToken

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NUMERIC_TOKEN = re.compile(r"(?<!\w)[<>≤≥]?\d+(?:[.,]\d+)?(?:[/-]\d+)*(?!\w)")


class EditabilityMetrics(BaseModel):
    """Static DOCX facts used to report editability."""

    model_config = ConfigDict(extra="forbid")

    editable_text_count: int = Field(ge=0)
    page_sized_raster_count: int = Field(ge=0)


def editability_metrics(path: Path) -> EditabilityMetrics:
    """Return editable text and full-page raster counts from DOCX XML."""

    inspection = inspect_docx(path)
    return EditabilityMetrics(
        editable_text_count=inspection.editable_text_count,
        page_sized_raster_count=inspection.page_sized_raster_count,
    )


def libreoffice_roundtrip_status(path: Path) -> str:
    """Return passed, failed, or unavailable for an optional office round-trip."""

    if find_libreoffice() is None:
        return "unavailable"
    with TemporaryDirectory(prefix="doc-eval-") as directory:
        try:
            _, reopened = roundtrip_docx(path, Path(directory))
            inspection = inspect_docx(reopened)
        except (OSError, RuntimeError, subprocess.CalledProcessError):
            return "failed"
    if inspection.editable_text_count == 0 or inspection.page_sized_raster_count:
        return "failed"
    return "passed"


class ReviewedRegion(BaseModel):
    """One manually reviewed source region used as an evaluation anchor."""

    model_config = ConfigDict(extra="forbid")

    region_id: str
    expected_text: str = Field(min_length=1)
    box: list[float] | None = Field(default=None, min_length=4, max_length=4)


class ReviewedAnchors(BaseModel):
    """Versioned, network-independent reviewed anchors for one document."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    regions: list[ReviewedRegion] = Field(min_length=1)
    critical_tokens: list[CriticalToken] = Field(default_factory=list)


def median_anchor_iou(audit_path: Path, anchors: ReviewedAnchors) -> float | None:
    """Return median IoU for reviewed boxes against output audit geometry."""

    audit = json.loads(audit_path.read_text())
    output_boxes = {
        region["region_id"]: region["geometry"] for region in audit.get("regions", [])
    }
    scores: list[float] = []
    for anchor in anchors.regions:
        if anchor.box is None or anchor.region_id not in output_boxes:
            continue
        expected_x, expected_y, expected_width, expected_height = anchor.box
        observed = output_boxes[anchor.region_id]
        observed_x = observed["x"]
        observed_y = observed["y"]
        observed_width = observed["width"]
        observed_height = observed["height"]
        left = max(expected_x, observed_x)
        top = max(expected_y, observed_y)
        right = min(expected_x + expected_width, observed_x + observed_width)
        bottom = min(expected_y + expected_height, observed_y + observed_height)
        intersection = max(0.0, right - left) * max(0.0, bottom - top)
        union = expected_width * expected_height + observed_width * observed_height - intersection
        scores.append(intersection / union if union else 0.0)
    return median(scores) if scores else None


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


def translation_anchor_accuracy(path: Path, anchors: ReviewedAnchors) -> float:
    """Return the fraction of reviewed anchors matching their editable output text."""

    text_by_bookmark = _bookmarked_text(path)
    matched = 0
    for region in anchors.regions:
        actual = text_by_bookmark.get(region.region_id.replace("-", "_"), "").strip()
        if actual == region.expected_text.strip():
            matched += 1
    return matched / len(anchors.regions)


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
