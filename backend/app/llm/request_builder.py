from __future__ import annotations

from typing import Any

MAX_EXCERPT_CHARS = 5000


def build_request(
    question: str,
    evidence: list[dict[str, Any]],
    *,
    data_level: str,
) -> dict[str, Any]:
    """Build citable documents and the exact evidence-index mapping sent to Anthropic."""
    approved = [
        item for item in evidence
        if item.get("review_status") == "approved"
        and item.get("license_status") == "approved"
        and str(item.get("excerpt", "")).strip()
    ]
    documents: list[dict[str, Any]] = []
    mapped_evidence: list[dict[str, Any]] = []
    for item in approved:
        title_parts = [str(item.get("title", "Nguồn đã duyệt")).strip()[:180]]
        version = item.get("document_version") or item.get("version")
        population = item.get("target_population") or item.get("population")
        if version:
            title_parts.append(str(version)[:80])
        if population:
            title_parts.append(str(population)[:100])
        excerpt = str(item["excerpt"])[:MAX_EXCERPT_CHARS]
        documents.append({
            "type": "document",
            "source": {
                "type": "text",
                "media_type": "text/plain",
                "data": excerpt,
            },
            "title": " | ".join(part for part in title_parts if part),
            "citations": {"enabled": True},
        })
        mapped_evidence.append({**item, "excerpt": excerpt})

    if data_level == "masked_question":
        task_text = (
            "Câu hỏi đã qua bước che số đo và định danh:\n"
            f"{question}\n\n"
            "Hãy chỉ giải thích khái niệm được hỏi bằng các tài liệu đính kèm. "
            "Không lặp lại hoặc tính toán kết quả cá nhân; kết quả do hệ thống viết riêng."
        )
    else:
        task_text = (
            "Hãy tóm tắt ngắn gọn các ý giáo dục chung trong tài liệu đính kèm. "
            "Không suy đoán câu hỏi của người dùng."
        )

    return {"documents": documents, "evidence": mapped_evidence, "task_text": task_text}
