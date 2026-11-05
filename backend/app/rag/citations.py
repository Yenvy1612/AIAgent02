from __future__ import annotations

from typing import Any

CITATION_FIELDS = ("citation_id", "document_id", "chunk_id", "title", "source_url", "page")


def validate_citations(evidence: list[dict[str, Any]], citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep citations only when they exactly match a retrieved approved evidence item."""
    approved = {
        tuple(item.get(field) for field in CITATION_FIELDS)
        for item in evidence
        if item.get("review_status") == "approved" and item.get("license_status") == "approved"
    }
    return [
        citation for citation in citations
        if tuple(citation.get(field) for field in CITATION_FIELDS) in approved
    ]
