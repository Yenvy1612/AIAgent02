from __future__ import annotations

import re
from typing import Any

from app.rag.citations import CITATION_FIELDS
from app.safety.keyword_rules import normalize_vi

_NUMBER = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?(?![\w])")
_URL = re.compile(r"https?://[^\s<>\]\[{}\"']+|\bwww\.[^\s<>\]\[{}\"']+", re.IGNORECASE)
_INLINE_CITATION = re.compile(r"\[C\d+\]", re.IGNORECASE)
_DIRECT_DIAGNOSIS = re.compile(
    r"\bban\s+(?:bi|mac)\s+(?:benh\s+)?(?:dai\s+thao\s+duong|tieu\s+duong)\b"
    r"|\byou\s+(?:have|are diagnosed with)\s+(?:diabetes|type\s*2\s+diabetes)\b"
)


def _value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _normalized_space(value: str) -> str:
    return " ".join(value.split())


def _numbers(value: str) -> set[str]:
    return {match.group(0).replace(",", ".") for match in _NUMBER.finditer(value)}


def _citation_dict(item: dict[str, Any]) -> dict[str, Any]:
    return {key: item.get(key) for key in CITATION_FIELDS}


def validate_response(response: Any, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    stop_reason = _value(response, "stop_reason")
    if stop_reason != "end_turn":
        reason = "STOP_REFUSAL" if stop_reason == "refusal" else "STOP_MAX_TOKENS" if stop_reason == "max_tokens" else "STOP_OTHER"
        return {"ok": False, "reason": reason, "answer": "", "citations": [], "stop_reason": stop_reason}

    text_blocks = [
        block for block in (_value(response, "content", []) or [])
        if _value(block, "type") == "text" and _value(block, "text")
    ]
    raw_text = "".join(str(_value(block, "text", "")) for block in text_blocks)
    control_text = raw_text.strip()
    if control_text == "KHONG_DU_BANG_CHUNG":
        return {"ok": False, "reason": "MODEL_INSUFFICIENT_EVIDENCE", "answer": "", "citations": [], "stop_reason": stop_reason}
    if not control_text:
        return {"ok": False, "reason": "CITATION_INVALID", "answer": "", "citations": [], "stop_reason": stop_reason}

    approved = [
        item for item in evidence
        if item.get("review_status") == "approved" and item.get("license_status") == "approved"
    ]
    visible_excerpts = [str(item.get("excerpt", "")) for item in approved]
    used: list[dict[str, Any]] = []
    used_by_chunk: dict[str, dict[str, Any]] = {}
    clean_blocks: list[tuple[str, list[str]]] = []
    uncited_chars = 0
    total_chars = 0

    for block in text_blocks:
        text = _INLINE_CITATION.sub("", str(_value(block, "text", "")))
        if not text:
            continue
        total_chars += len(text)
        references = _value(block, "citations", []) or []
        if not references:
            uncited_chars += len(text)
            clean_blocks.append((text, []))
            continue

        labels: list[str] = []
        for reference in references:
            document_index = _value(reference, "document_index")
            cited_text = _value(reference, "cited_text")
            if (
                not isinstance(document_index, int)
                or isinstance(document_index, bool)
                or document_index < 0
                or document_index >= len(approved)
                or not isinstance(cited_text, str)
                or not cited_text.strip()
                or _normalized_space(cited_text) not in _normalized_space(visible_excerpts[document_index])
            ):
                return {"ok": False, "reason": "CITATION_INVALID", "answer": "", "citations": [], "stop_reason": stop_reason}
            source = approved[document_index]
            chunk_id = str(source.get("chunk_id", ""))
            if chunk_id not in used_by_chunk:
                used_by_chunk[chunk_id] = _citation_dict(source)
                used.append(used_by_chunk[chunk_id])
            label = f"C{list(used_by_chunk).index(chunk_id) + 1}"
            if label not in labels:
                labels.append(label)
        clean_blocks.append((text, labels))

    if not used:
        return {"ok": False, "reason": "CITATION_INVALID", "answer": "", "citations": [], "stop_reason": stop_reason}
    if total_chars and uncited_chars / total_chars > 0.30:
        return {"ok": False, "reason": "LOW_CITATION_COVERAGE", "answer": "", "citations": [], "stop_reason": stop_reason}

    answer_text = "".join(text for text, _ in clean_blocks)
    source_text = "\n".join(visible_excerpts)
    if not _numbers(answer_text).issubset(_numbers(source_text)):
        return {"ok": False, "reason": "UNSUPPORTED_NUMBER", "answer": "", "citations": [], "stop_reason": stop_reason}

    allowed_urls = {
        str(item.get("source_url", "")).rstrip(".,);]")
        for item in approved if item.get("source_url")
    }
    if any(match.group(0).rstrip(".,);]") not in allowed_urls for match in _URL.finditer(answer_text)):
        return {"ok": False, "reason": "UNSUPPORTED_URL", "answer": "", "citations": [], "stop_reason": stop_reason}

    if _DIRECT_DIAGNOSIS.search(normalize_vi(answer_text)):
        return {"ok": False, "reason": "DIAGNOSTIC_CLAIM", "answer": "", "citations": [], "stop_reason": stop_reason}

    rendered = [text + "".join(f"[{label}]" for label in labels) for text, labels in clean_blocks]
    return {
        "ok": True,
        "reason": "OK",
        "answer": "".join(rendered),
        "citations": used,
        "stop_reason": stop_reason,
    }
