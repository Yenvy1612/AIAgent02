from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.agent.graph import run_agent  # noqa: E402
from app.rag.chunker import chunk_page, chunk_pages, lexical_token_count  # noqa: E402
from app.rag.loader import _extraction_status, source_sha256  # noqa: E402
from app.rag.retriever import KnowledgeBase  # noqa: E402
from app.safety.keyword_rules import medication_request, wound_care_request  # noqa: E402
from ingest_kb import build_index  # noqa: E402

FIELDS = [
    "source_code", "title", "organization", "source_url", "local_path", "topic",
    "trust_level", "license_status", "review_status", "content_sha256",
]
AMENDED_PAGE = {
    "page": 39,
    "text": "b) Chế độ insulin nền – nhanh là lựa chọn,\n   insulin trộn không được khuyến cáo sử dụng thường quy.\n",
    "extraction_status": "text_extracted",
}
REPLACEMENT = {
    "pdf_page": 39,
    "find": "Chế độ insulin nền – nhanh là lựa chọn, insulin trộn không được khuyến cáo sử dụng thường quy.",
    "replace": "Chế độ insulin nền – nhanh, trộn hỗn hợp là các lựa chọn.",
    "authority": "KB-01A",
}


def _approved_manifest(tmp_path: Path, source: Path, content_sha256: str | None = None) -> Path:
    manifest = tmp_path / "sources.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow({
            "source_code": "KB-X", "title": "Reviewed", "organization": "Example",
            "local_path": str(source), "topic": "diagnosis", "license_status": "approved",
            "review_status": "approved",
            "content_sha256": source_sha256(source) if content_sha256 is None else content_sha256,
        })
    return manifest


def _metadata(tmp_path: Path, **fields) -> Path:
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps({"documents": [{"source_code": "KB-X", **fields}]}), encoding="utf-8")
    return path


def _fake_pages(monkeypatch, pages: list[dict]) -> None:
    monkeypatch.setattr("ingest_kb.load_document", lambda _: ([dict(page) for page in pages], {}))


def _source(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr("ingest_kb.ROOT", tmp_path)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"fixture")
    return source


def test_ingest_requires_a_content_hash_for_approved_sources(tmp_path: Path, monkeypatch):
    source = _source(tmp_path, monkeypatch)
    result = build_index(
        _approved_manifest(tmp_path, source, content_sha256=""), tmp_path / "index.json",
        tmp_path / "metadata.json", token_counter=lexical_token_count,
    )
    assert result["chunks"] == []
    assert result["blocked_sources"] == [{"source_code": "KB-X", "reason": "missing content_sha256"}]


def test_ingest_replaces_amended_wording_across_line_breaks(tmp_path: Path, monkeypatch):
    source = _source(tmp_path, monkeypatch)
    _fake_pages(monkeypatch, [AMENDED_PAGE])
    result = build_index(
        _approved_manifest(tmp_path, source), tmp_path / "index.json",
        _metadata(tmp_path, text_replacements=[REPLACEMENT]), token_counter=lexical_token_count,
    )
    text = result["chunks"][0]["text"]
    assert "không được khuyến cáo" not in text
    assert "trộn hỗn hợp là các lựa chọn" in text


def test_ingest_blocks_the_source_when_amended_wording_is_not_found(tmp_path: Path, monkeypatch):
    source = _source(tmp_path, monkeypatch)
    _fake_pages(monkeypatch, [{**AMENDED_PAGE, "text": "Nội dung khác hẳn trên trang này."}])
    result = build_index(
        _approved_manifest(tmp_path, source), tmp_path / "index.json",
        _metadata(tmp_path, text_replacements=[REPLACEMENT]), token_counter=lexical_token_count,
    )
    assert result["chunks"] == []
    assert "text_replacement matched 0 times" in result["blocked_sources"][0]["reason"]


def test_real_kb01_amendment_passage_is_replaced():
    """Guards the reviewed QĐ 1353 wording against the actual source PDF and metadata."""
    metadata = json.loads((ROOT / "kb_manifest" / "document_metadata.json").read_text(encoding="utf-8"))
    kb01 = next(item for item in metadata["documents"] if item["source_code"] == "KB-01")
    path = ROOT / kb01["local_path"]
    if not path.is_file():
        return
    from app.rag.loader import load_pdf
    from ingest_kb import _apply_text_replacements

    pages = load_pdf(path)
    _apply_text_replacements(pages, kb01["text_replacements"])
    text = " ".join(next(page for page in pages if page["page"] == 39)["text"].split())
    assert "insulin trộn không được khuyến cáo" not in text
    assert "trộn hỗn hợp (tiêm dưới da) là các lựa chọn" in text


def test_ingest_one_unreadable_source_does_not_stop_the_build(tmp_path: Path, monkeypatch):
    source = _source(tmp_path, monkeypatch)

    def fail(_):
        raise RuntimeError("Unsupported KB source type: .docx")

    monkeypatch.setattr("ingest_kb.load_document", fail)
    result = build_index(
        _approved_manifest(tmp_path, source), tmp_path / "index.json",
        tmp_path / "metadata.json", token_counter=lexical_token_count,
    )
    assert result["blocked_sources"] == [{"source_code": "KB-X", "reason": "load failed (RuntimeError)"}]


def test_ingest_applies_page_exclusions_topics_and_reports_unreadable_pages(tmp_path: Path, monkeypatch):
    source = _source(tmp_path, monkeypatch)
    body = "Nội dung có đủ số từ để tạo thành một đoạn hợp lệ trong chỉ mục."
    _fake_pages(monkeypatch, [
        {"page": 1, "text": "Nơi nhận: " + body, "extraction_status": "text_extracted"},
        {"page": 2, "text": body, "extraction_status": "text_extracted"},
        {"page": 3, "text": "21", "extraction_status": "no_text_ocr_review_required"},
        {"page": 4, "text": "%3ȲPP+J", "extraction_status": "unmapped_glyphs_review_required"},
        {"page": 5, "text": body, "extraction_status": "text_extracted"},
    ])
    result = build_index(
        _approved_manifest(tmp_path, source), tmp_path / "index.json",
        _metadata(tmp_path, exclude_pages=[1], topic_by_page=[{"from": 5, "to": 5, "topic": "hypoglycemia"}], is_active=False),
        token_counter=lexical_token_count,
    )
    assert [(chunk["page"], chunk["topic"]) for chunk in result["chunks"]] == [(2, "diagnosis"), (5, "hypoglycemia")]
    assert result["pages_needing_manual_review"] == [{"source_code": "KB-X", "pdf_pages": [3, 4]}]
    assert all(chunk["is_active"] is False for chunk in result["chunks"])


def test_chunker_detects_line_headings_and_carries_them_to_the_next_page():
    pages = [
        {"page": 1, "text": "PHẦN 6 HẠ ĐƯỜNG HUYẾT\nHạ glucose huyết là biến chứng cấp tính.\n1.1. Triệu chứng\nRun tay và vã mồ hôi."},
        {"page": 2, "text": "Tiếp tục theo dõi người bệnh sau khi xử trí."},
    ]
    chunks = chunk_pages(pages, token_counter=lexical_token_count)
    assert chunks[0]["section"] == "PHẦN 6 HẠ ĐƯỜNG HUYẾT / 1.1. Triệu chứng"
    assert chunks[1]["section"] == "1.1. Triệu chứng"


def test_chunker_does_not_treat_body_text_as_headings():
    text = "Mục tiêu điều trị được cá thể hóa cho từng người bệnh.\nĐiều trị bằng insulin khi cần\nphần lớn người bệnh đáp ứng"
    chunks = chunk_page(text, 1, token_counter=lexical_token_count)
    assert chunks[0]["section"] is None


def test_extraction_status_flags_image_pages_and_unmapped_glyphs():
    assert _extraction_status("21", has_images=True) == "no_text_ocr_review_required"
    assert _extraction_status("", has_images=False) == "no_text_ocr_review_required"
    assert _extraction_status("SHUVLVWHQW%3ȲPP+J &RQVLGHU%3ȲPP+J UHGXFH%3ȲPP+J", has_images=False) == "unmapped_glyphs_review_required"
    assert _extraction_status("HbA1c ≥ 6,5% (48 mmol/mol) với BMI 23 kg/m2.", has_images=False) == "text_extracted"


def test_local_search_refuses_out_of_scope_queries_and_keeps_in_scope_ones(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DIACARE_RAG_MODE", "local")
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"chunks": [{
        "chunk_id": "KB-X-1", "document_id": "KB-X", "title": "T", "topic": "diagnosis",
        "text": "Chẩn đoán đái tháo đường dựa vào glucose. Cổ phiếu là từ không liên quan.",
        "review_status": "approved", "license_status": "approved", "is_active": True,
    }]}), encoding="utf-8")
    kb = KnowledgeBase(index)
    refused = kb.search("Giá cổ phiếu Apple hôm nay là bao nhiêu?")
    assert refused["status"] == "INSUFFICIENT_EVIDENCE"
    assert refused["degraded_reason"] == "QUERY_OUT_OF_KB_SCOPE"
    assert kb.search("Chẩn đoán đái tháo đường thế nào?")["status"] == "OK"


def test_vector_search_drops_results_below_the_rerank_threshold(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DIACARE_RAG_MIN_RERANK_SCORE", "0")
    chunk = {
        "chunk_id": "KB-X-1", "document_id": "KB-X", "title": "T", "topic": "diagnosis",
        "text": "Chẩn đoán đái tháo đường.", "review_status": "approved", "license_status": "approved",
    }
    hits = [{"payload": {"chunk_id": "KB-X-1"}, "score": 0.9}]

    class FakeEmbedder:
        def encode(self, texts):
            return [[0.0] for _ in texts]

    monkeypatch.setattr("app.rag.retriever.get_embedding_provider", lambda: FakeEmbedder())
    monkeypatch.setattr("app.rag.retriever.vector_store.search", lambda *args, **kwargs: hits)
    kb = KnowledgeBase(tmp_path / "unused.json")
    monkeypatch.setattr("app.rag.retriever.reranker.score", lambda query, documents: [-3.0])
    assert kb._vector_search("đái tháo đường", None, 5, [chunk])["status"] == "INSUFFICIENT_EVIDENCE"
    monkeypatch.setattr("app.rag.retriever.reranker.score", lambda query, documents: [2.0])
    assert kb._vector_search("đái tháo đường", None, 5, [chunk])["status"] == "OK"


def test_vector_search_refuses_out_of_scope_queries_before_loading_models(tmp_path: Path, monkeypatch):
    def fail():
        raise AssertionError("An out-of-scope query must not reach the embedding model")

    monkeypatch.setattr("app.rag.retriever.get_embedding_provider", fail)
    result = KnowledgeBase(tmp_path / "unused.json")._vector_search("Giá cổ phiếu Apple hôm nay?", None, 5, [])
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["degraded_reason"] == "QUERY_OUT_OF_KB_SCOPE"


@pytest.mark.parametrize("message", [
    "Nên xử trí vết loét bàn chân tại nhà thế nào?",
    "Bàn chân tôi có vết loét, tự bôi gì cho lành?",
    "How do I treat a foot ulcer at home?",
    "Thuốc không có trong KB có chữa khỏi đái tháo đường không?",
    "Thuốc nào chữa dứt điểm tiểu đường?",
])
def test_self_treatment_and_cure_claims_are_refused(message):
    result = run_agent(message, None, None)
    assert result["status"] == "CLINICAL_REVIEW"
    assert result["citations"] == []


@pytest.mark.parametrize("message", [
    "Cách chăm sóc bàn chân cho người đái tháo đường?",
    "Vì sao người đái tháo đường dễ bị loét bàn chân?",
    "Làm sao phòng ngừa loét bàn chân?",
    "Tôi chưa bị loét bàn chân, cần lưu ý gì?",
    "Đái tháo đường có chữa được không?",
    "Thuốc này chưa được phê duyệt à?",
])
def test_general_education_questions_are_not_treated_as_self_treatment(message):
    assert not wound_care_request(message)
    if "Thuốc" not in message:
        assert not medication_request(message)
