from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.citations import validate_citations  # noqa: E402


def test_citations_must_exactly_match_a_retrieved_approved_chunk():
    approved = {
        "citation_id": "C1", "document_id": "KB-TEST", "chunk_id": "KB-TEST-001",
        "title": "Reviewed source", "source_url": "https://example.org/source", "page": 2,
        "review_status": "approved", "license_status": "approved",
    }
    valid = {key: approved[key] for key in (
        "citation_id", "document_id", "chunk_id", "title", "source_url", "page",
    )}
    forged = {**valid, "title": "Forged title"}
    candidate = {**approved, "chunk_id": "KB-TEST-002", "review_status": "candidate"}
    candidate_citation = {**valid, "chunk_id": "KB-TEST-002"}
    assert validate_citations([approved, candidate], [valid, forged, candidate_citation]) == [valid]
