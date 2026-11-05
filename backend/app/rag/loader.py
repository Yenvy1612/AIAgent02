from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


# Runs of a custom font without a Unicode map, such as "%3ȲPP+J" for "BP ≥ mmHg". The digits are lost.
UNMAPPED_GLYPH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z0-9]*[%$&+\]\\Ȳ][A-Z0-9%$&+\]\\Ȳ]*[A-Z][A-Z0-9%$&+\]\\Ȳ]*")
MIN_UNMAPPED_GLYPH_RUNS = 3
MIN_IMAGE_PAGE_CHARS = 30


def _page_text(page: Any) -> str:
    """Extract page text without diagonal digital-signature stamps.

    Coordinate sorting keeps table rows together on upright pages, but it interleaves stamp
    characters into body text and scrambles rotated pages, so those use the PDF's reading order.
    """
    lines = [line for block in page.get_text("dict")["blocks"] for line in block.get("lines", [])]
    stamps = [
        "".join(span["text"] for span in line["spans"]).strip()
        for line in lines
        if abs(line["dir"][0]) > 0.1 and abs(line["dir"][1]) > 0.1
    ]
    upright = all(line["dir"][0] > 0.99 for line in lines)
    text = page.get_text("text", sort=upright and not stamps)
    for stamp in stamps:
        if stamp:
            text = text.replace(stamp, "")
    return text


def _extraction_status(text: str, has_images: bool) -> str:
    stripped = text.strip()
    if not stripped or (has_images and len(stripped) < MIN_IMAGE_PAGE_CHARS):
        return "no_text_ocr_review_required"
    if len(UNMAPPED_GLYPH_RE.findall(text)) >= MIN_UNMAPPED_GLYPH_RUNS:
        return "unmapped_glyphs_review_required"
    return "text_extracted"


def load_pdf(path: Path) -> list[dict[str, Any]]:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("Install the pinned PyMuPDF package from backend/requirements-rag.txt.") from exc
    pages = []
    with pymupdf.open(path) as document:
        for page in document:
            text = _page_text(page)
            pages.append({
                "page": page.number + 1,
                "text": text,
                "extraction_status": _extraction_status(text, bool(page.get_images())),
            })
    return pages


def load_web_html(html: str, url: str = "") -> str:
    try:
        import trafilatura
    except ImportError as exc:
        raise RuntimeError("Install the pinned Trafilatura package from backend/requirements-rag.txt.") from exc
    extracted = trafilatura.extract(
        html,
        url=url or None,
        include_comments=False,
        include_tables=True,
        include_links=True,
        output_format="markdown",
        favor_precision=True,
    )
    return extracted or ""


def load_markdown(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    front_matter: dict[str, Any] = {}
    body = raw
    if raw.startswith("---\n"):
        _, _, remainder = raw.partition("---\n")
        header, separator, body = remainder.partition("\n---\n")
        if separator:
            try:
                import yaml
                front_matter = yaml.safe_load(header) or {}
            except ImportError:
                for line in header.splitlines():
                    key, divider, value = line.partition(":")
                    if divider:
                        front_matter[key.strip()] = value.strip().strip('"')
    return [{"page": None, "text": body, "extraction_status": "snapshot_text"}], front_matter


def load_document(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return load_pdf(path), {}
    if suffix in {".md", ".txt"}:
        return load_markdown(path)
    if suffix in {".html", ".htm"}:
        html = path.read_text(encoding="utf-8")
        text = load_web_html(html)
        return [{"page": None, "text": text, "extraction_status": "trafilatura"}], {}
    raise RuntimeError(f"Unsupported KB source type: {path.suffix}")


def source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
