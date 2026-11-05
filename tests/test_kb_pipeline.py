from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.rag.chunker import TOKEN_RE, chunk_page, lexical_token_count  # noqa: E402
from app.rag.loader import source_sha256  # noqa: E402
from ingest_kb import build_index  # noqa: E402
from evaluate_rag import evaluate_gold_questions  # noqa: E402
from snapshot_web_sources import snapshot_sources  # noqa: E402


def test_chunker_observes_token_target_and_preserves_exceptions_and_tables():
    statements = [f"Tiêu chí số {i} được áp dụng trong nhóm người trưởng thành." for i in range(75)]
    body = "## Mục chẩn đoán\n\n" + " ".join(statements)
    body += " Tiêu chí này áp dụng cho nhóm A. Ngoại trừ trường hợp có triệu chứng cấp tính."
    body += "\n\n| Xét nghiệm | Ngưỡng | Đơn vị |\n|---|---:|---|\n| HbA1c | 6,5 | % |"
    chunks = chunk_page(body, 11, token_counter=lexical_token_count)
    assert len(chunks) >= 2
    assert all(chunk["token_count"] <= 600 for chunk in chunks)
    assert all(chunk["page"] == 11 for chunk in chunks)
    assert any("Tiêu chí này áp dụng cho nhóm A. Ngoại trừ trường hợp" in chunk["text"] for chunk in chunks)
    assert any("HbA1c | 6,5 | %" in chunk["text"] for chunk in chunks)
    assert any(chunk["section"] == "Mục chẩn đoán" for chunk in chunks)

    token_lists = [TOKEN_RE.findall(chunk["text"]) for chunk in chunks]
    overlaps = []
    for previous, current in zip(token_lists, token_lists[1:]):
        overlap = 0
        for size in range(1, min(len(previous), len(current)) + 1):
            if previous[-size:] == current[:size]:
                overlap = size
        overlaps.append(overlap)
    assert all(60 <= overlap <= 80 for overlap in overlaps)


def test_ingest_blocks_candidate_sources_even_when_file_exists(tmp_path: Path):
    source = tmp_path / "candidate.md"
    source.write_text("# Candidate\n\nSome text.", encoding="utf-8")
    manifest = tmp_path / "sources.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "source_code", "title", "organization", "source_url", "local_path", "topic",
            "trust_level", "license_status", "review_status", "content_sha256",
        ])
        writer.writeheader()
        writer.writerow({
            "source_code": "KB-X", "title": "Candidate", "organization": "Example",
            "local_path": str(source), "topic": "education", "license_status": "approved",
            "review_status": "candidate",
        })
    output = tmp_path / "index.json"
    result = build_index(
        manifest, output, tmp_path / "metadata.json", token_counter=lexical_token_count,
    )
    assert result["chunks"] == []
    assert result["blocked_sources"] == [{"source_code": "KB-X", "reason": "review_status=candidate"}]
    assert json.loads(output.read_text(encoding="utf-8"))["chunks"] == []


def test_ingest_reports_eligible_and_blocked_source_names(tmp_path: Path, capsys, monkeypatch):
    eligible = tmp_path / "eligible.md"
    eligible.write_text("# Reviewed\n\nThis approved source contains enough text to create a small chunk.", encoding="utf-8")
    candidate = tmp_path / "candidate.md"
    candidate.write_text("# Candidate\n\nNot approved for indexing.", encoding="utf-8")
    manifest = tmp_path / "sources.csv"
    fields = [
        "source_code", "title", "organization", "source_url", "local_path", "topic",
        "trust_level", "license_status", "review_status", "content_sha256",
    ]
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "source_code": "KB-OK", "title": "Reviewed", "organization": "Example",
            "local_path": str(eligible), "topic": "education", "license_status": "approved",
            "review_status": "approved",
        })
        writer.writerow({
            "source_code": "KB-X", "title": "Candidate", "organization": "Example",
            "local_path": str(candidate), "topic": "education", "license_status": "approved",
            "review_status": "candidate",
        })

    rows = list(csv.DictReader(manifest.open(encoding="utf-8", newline="")))
    rows[0]["content_sha256"] = source_sha256(eligible)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    monkeypatch.setattr("ingest_kb.ROOT", tmp_path)
    result = build_index(
        manifest, tmp_path / "index.json", tmp_path / "metadata.json",
        token_counter=lexical_token_count,
    )
    output = capsys.readouterr().out
    assert "ELIGIBLE KB-OK:" in output
    assert "BLOCKED KB-X:" in output
    assert "1 sources ELIGIBLE, 1 sources BLOCKED" in output
    assert [chunk["document_id"] for chunk in result["chunks"]] == ["KB-OK"]


def test_snapshot_saves_front_matter_and_does_not_approve(tmp_path: Path):
    manifest = tmp_path / "sources.csv"
    fields = ["source_code", "title", "organization", "source_url", "local_path", "document_type", "language", "topic", "license_status", "review_status", "content_sha256"]
    row = {
        "source_code": "KB-25", "title": "Meal Planning", "organization": "CDC",
        "source_url": "https://example.org/meal", "document_type": "web", "language": "en",
        "topic": "nutrition", "license_status": "approved", "review_status": "candidate",
    }
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)
    candidates = tmp_path / "candidates"
    result = snapshot_sources(
        manifest, candidates, accessed_on=date(2026, 11, 3),
        fetch=lambda _: "<html><body><main><h1>Meal planning</h1><p>Build balanced meals.</p></main></body></html>",
        root_dir=tmp_path,
    )
    assert len(result["saved"]) == 1
    snapshot = candidates / "KB-25_2026-11-03.md"
    content = snapshot.read_text(encoding="utf-8")
    assert content.startswith("---\nsource_code: KB-25\n")
    assert "content_sha256:" in content and "Build balanced meals." in content
    with manifest.open(encoding="utf-8", newline="") as handle:
        saved = next(csv.DictReader(handle))
    assert saved["review_status"] == "candidate"
    assert saved["license_status"] == "approved"
    assert saved["local_path"] == "candidates/KB-25_2026-11-03.md"
    assert saved["content_sha256"]


def test_gold_set_has_30_structured_cases_and_marks_unapproved_sources_blocked():
    data = json.loads((ROOT / "evaluation" / "rag" / "gold_questions.json").read_text(encoding="utf-8"))
    questions = data["questions"]
    assert len(questions) == 30
    required = {
        "question", "topic", "expected_document_ids", "gold_answer", "expected_citations",
        "must_refuse", "safety_level", "blocked_until_approved",
    }
    assert all(required.issubset(row) for row in questions)
    assert {row["id"] for row in questions[:10]} == {f"KB-T{i:02d}" for i in range(1, 11)}
    assert all(row["gold_answer"] is None for row in questions if row["blocked_until_approved"])
    assert not next(row for row in questions if row["id"] == "KB-T08")["blocked_until_approved"]


def test_kb_evaluator_blocks_unmapped_and_unapproved_gold_sources(tmp_path: Path):
    cases_path = tmp_path / "gold_questions.json"
    cases_path.write_text(json.dumps({"questions": [
        {
            "id": "unmapped", "question": "Question without a source", "topic": "general",
            "expected_document_ids": [], "must_refuse": False, "safety_level": "NORMAL",
            "blocked_until_approved": True,
        },
        {
            "id": "unapproved", "question": "Question with a candidate source", "topic": "general",
            "expected_document_ids": ["KB-X"], "must_refuse": False, "safety_level": "NORMAL",
            "blocked_until_approved": False,
        },
    ]}), encoding="utf-8")

    class EmptyKnowledgeBase:
        def __init__(self, index_path):
            pass

        def _approved_chunks(self):
            return []

        def search(self, *args, **kwargs):
            return {"evidence": []}

    with patch("evaluate_rag.KnowledgeBase", EmptyKnowledgeBase), patch(
        "evaluate_rag.run_agent",
        return_value={"answer": "Không đủ thông tin đáng tin cậy.", "citations": [], "status": "DEGRADED"},
    ):
        report = evaluate_gold_questions(cases_path, tmp_path / "empty-index.json")

    assert report["blocked_until_approved_count"] == 2
    assert report["retrieval_case_count"] == 0
    assert report["recall_at_5"] is None
    assert all(row["blocked_until_approved"] for row in report["results"])
