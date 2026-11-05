from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.chunker import chunk_pages, lexical_token_count  # noqa: E402
from app.rag.loader import load_document, source_sha256  # noqa: E402

MANIFEST = ROOT / "kb_manifest" / "sources.csv"
DOCUMENT_METADATA = ROOT / "kb_manifest" / "document_metadata.json"
OUTPUT = ROOT / "data" / "kb" / "index.json"
MIN_CHUNK_TOKENS = 8


class KBContentError(RuntimeError):
    """A reviewed content instruction could not be applied to its source."""


def _load_token_counter() -> tuple[Callable[[str], int], str]:
    model_path = os.getenv("DIACARE_BGE_M3_MODEL_PATH", "").strip()
    if model_path:
        try:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            return (lambda text: len(tokenizer.encode(text, add_special_tokens=False))), "local_transformers_tokenizer"
        except Exception as exc:
            print(f"WARN tokenizer unavailable ({type(exc).__name__}); using Unicode word/punctuation estimate")
    return lexical_token_count, "unicode_word_punctuation_estimate"


def _reason_blocked(row: dict[str, str], source_path: Path | None = None) -> str | None:
    if row.get("review_status") != "approved":
        return f"review_status={row.get('review_status') or 'missing'}"
    if row.get("license_status") != "approved":
        return f"license_status={row.get('license_status') or 'missing'}"
    local_path = (row.get("local_path") or "").strip()
    if not local_path:
        return "no local_path"
    if source_path is None:
        return "missing local file"
    expected = (row.get("content_sha256") or "").strip().lower()
    if not expected:
        return "missing content_sha256"
    if expected != source_sha256(source_path):
        return "content_sha256 mismatch"
    return None


def _pattern_for(find: str) -> re.Pattern[str]:
    """Match reviewed wording across PDF line breaks and layout spacing."""
    return re.compile(r"\s+".join(re.escape(word) for word in find.split()))


def _apply_text_replacements(pages: list[dict[str, Any]], replacements: list[dict[str, Any]]) -> None:
    """Apply reviewed amendments; a missing passage must never leave the old wording indexed."""
    for item in replacements:
        target = next((page for page in pages if page.get("page") == item.get("pdf_page")), None)
        if target is None:
            raise KBContentError(f"text_replacement page {item.get('pdf_page')} not found")
        updated, count = _pattern_for(item["find"]).subn(lambda _: item["replace"], target["text"])
        if count != 1:
            raise KBContentError(f"text_replacement matched {count} times on page {item.get('pdf_page')}")
        target["text"] = updated


def _topic_for_page(row: dict[str, str], doc_meta: dict[str, Any], page: int | None) -> str:
    for item in doc_meta.get("topic_by_page", []):
        if page is not None and item["from"] <= page <= item["to"]:
            return item["topic"]
    return row["topic"]


def _document_chunks(
    row: dict[str, str],
    source_path: Path,
    doc_meta: dict[str, Any],
    token_counter: Callable[[str], int],
    token_count_method: str,
) -> tuple[list[dict[str, Any]], list[int]]:
    digest = source_sha256(source_path)
    pages, snapshot_meta = load_document(source_path)
    _apply_text_replacements(pages, doc_meta.get("text_replacements", []))
    excluded = set(doc_meta.get("exclude_pages", []))
    unreadable: list[int] = []
    usable: list[dict[str, Any]] = []
    for page_record in pages:
        page = page_record.get("page")
        if page in excluded:
            continue
        status = page_record.get("extraction_status")
        if status in {"no_text_ocr_review_required", "unmapped_glyphs_review_required"}:
            unreadable.append(page)
            print(f"WARN {row['source_code']} PDF page {page} skipped ({status}); manual review required")
            continue
        usable.append(page_record)

    amended_sections = doc_meta.get("amended_sections", [])
    # Pages are chunked together so a section title carries over to the following page.
    records = chunk_pages(usable, min_tokens=350, max_tokens=600, overlap_tokens=70, token_counter=token_counter)
    chunks: list[dict[str, Any]] = []
    for chunk in records:
        if chunk["token_count"] < MIN_CHUNK_TOKENS:
            continue
        page = chunk["page"]
        amended_record = next((item for item in amended_sections if item.get("pdf_page") == page), None)
        text = chunk["text"]
        chunks.append({
            "chunk_id": f"{row['source_code']}-{digest[:8]}-{page or 0:03d}-{len(chunks) + 1:04d}",
            "document_id": row["source_code"],
            "title": row["title"],
            "organization": row["organization"],
            "source_url": row.get("source_url") or snapshot_meta.get("url"),
            "page": page,
            "section": chunk.get("section"),
            "topic": _topic_for_page(row, doc_meta, page),
            "trust_level": row.get("trust_level"),
            "document_version": doc_meta.get("document_version") or row.get("document_version"),
            "language": doc_meta.get("language") or row.get("language"),
            "population": doc_meta.get("population") or "unspecified",
            "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "source_sha256": digest,
            "token_count": chunk["token_count"],
            "token_count_method": token_count_method,
            "supersedes": doc_meta.get("supersedes", []),
            "amended_by": doc_meta.get("amended_by", []),
            "amended": amended_record is not None,
            "amended_section": amended_record.get("section") if amended_record else None,
            "review_status": "approved",
            "license_status": "approved",
            "is_active": bool(doc_meta.get("is_active", True)),
            "text": text,
        })
    return chunks, unreadable


def build_index(
    manifest_path: Path = MANIFEST,
    output_path: Path = OUTPUT,
    metadata_path: Path = DOCUMENT_METADATA,
    *,
    token_counter: Callable[[str], int] | None = None,
    token_count_method: str | None = None,
) -> dict[str, Any]:
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    document_metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {"documents": []}
    by_code = {item.get("source_code"): item for item in document_metadata.get("documents", [])}
    if token_counter is None:
        token_counter, detected_method = _load_token_counter()
        token_count_method = token_count_method or detected_method
    token_count_method = token_count_method or "injected_token_counter"

    indexed: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    eligible_sources: list[str] = []
    manual_review: list[dict[str, Any]] = []
    for row in rows:
        local_path = (row.get("local_path") or "").strip()
        resolved_path = (ROOT / local_path).resolve() if local_path else None
        inside_root = bool(resolved_path and resolved_path.is_relative_to(ROOT.resolve()))
        source_path = resolved_path if inside_root and resolved_path.is_file() else None
        reason = _reason_blocked(row, source_path)
        if reason:
            record = {"source_code": row.get("source_code", ""), "reason": reason}
            blocked.append(record)
            print(f"BLOCKED {record['source_code']}: {reason}")
            continue

        assert source_path is not None
        doc_meta = by_code.get(row["source_code"], {})
        try:
            chunks, unreadable = _document_chunks(row, source_path, doc_meta, token_counter, token_count_method)
        except Exception as exc:
            # One unreadable source must not stop the others, and it contributes no partial chunks.
            detail = str(exc) if isinstance(exc, KBContentError) else f"load failed ({type(exc).__name__})"
            blocked.append({"source_code": row["source_code"], "reason": detail})
            print(f"BLOCKED {row['source_code']}: {detail}")
            continue
        eligible_sources.append(row["source_code"])
        print(f"ELIGIBLE {row['source_code']}: review, license, local file, and content hash checks passed")
        indexed.extend(chunks)
        if unreadable:
            manual_review.append({"source_code": row["source_code"], "pdf_pages": unreadable})
        print(f"INGEST {row['source_code']}: {len(chunks)} chunks")

    result = {
        "index_version": "4",
        "retrieval_mode": "hybrid-configurable",
        "chunking": {"min_tokens": 350, "max_tokens": 600, "overlap_tokens": 70, "token_count_method": token_count_method},
        "blocked_sources": blocked,
        "pages_needing_manual_review": manual_review,
        "chunks": indexed,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote {len(indexed)} chunks to {output_path}; "
        f"{len(eligible_sources)} sources ELIGIBLE, {len(blocked)} sources BLOCKED"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest only approved KB sources into the local prototype index.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--metadata", type=Path, default=DOCUMENT_METADATA)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build_index(args.manifest, args.output, args.metadata)


if __name__ == "__main__":
    main()
