from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.graph import run_agent
from app.rag.retriever import KnowledgeBase


def is_evidence_refusal(response: dict) -> bool:
    if response.get("citations"):
        return False
    answer = response.get("answer", "").casefold()
    refusal_markers = (
        "không đủ thông tin đáng tin cậy",
        "chưa có nguồn chẩn đoán đã được phê duyệt",
        "không thể diễn giải ngưỡng hiện tại",
        "không thể trả lời câu hỏi này",
    )
    return any(marker in answer for marker in refusal_markers)


def evaluate_gold_questions(cases_path: Path, index_path: Path) -> dict:
    # G3 measures the approved KB only, so the unreviewed web fallback stays out of this run.
    os.environ["DIACARE_WEB_SEARCH_ENABLED"] = "false"
    cases_data = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = cases_data.get("questions", [])
    kb = KnowledgeBase(index_path)
    approved_ids = {chunk.get("document_id") for chunk in kb._approved_chunks()}
    approved_count = len(approved_ids)
    rows = []
    refusal_rows = []
    retrieval_hits = 0
    expected_relevant = 0
    precision_sum = 0.0
    reciprocal_rank_sum = 0.0
    retrieval_case_count = 0
    citation_total = 0
    citation_valid = 0

    for case in cases:
        expected_docs = set(case.get("expected_document_ids", []))
        expected_docs_approved = bool(expected_docs) and expected_docs.issubset(approved_ids)
        # A source-dependent question remains blocked whenever its expected
        # source is unavailable, even if the gold row forgot the flag. Rows
        # without a mapped source stay blocked when explicitly marked so.
        blocked = (
            bool(expected_docs) and not expected_docs_approved
        ) or (bool(case.get("blocked_until_approved")) and not expected_docs)
        query = case["question"]
        search = kb.search(query, case.get("topic"), top_k=5)
        evidence = search.get("evidence", [])[:5]
        retrieved_ids = [item.get("document_id") for item in evidence]
        hits = len(expected_docs.intersection(retrieved_ids))
        retrieval_eligible = bool(expected_docs) and not blocked and expected_docs_approved and approved_count > 0
        rank = next((index + 1 for index, document_id in enumerate(retrieved_ids) if document_id in expected_docs), None)
        if retrieval_eligible:
            retrieval_case_count += 1
            expected_relevant += len(expected_docs)
            retrieval_hits += hits
            precision_sum += hits / 5
            reciprocal_rank_sum += 1 / rank if rank else 0.0

        with patch(
            "app.agent.graph.search_kb",
            side_effect=lambda query, topic=None, top_k=5: kb.search(query, topic, top_k),
        ):
            response = run_agent(query, None, None)
        evidence_keys = {
            tuple(item.get(key) for key in ("citation_id", "document_id", "chunk_id", "title", "source_url", "page"))
            for item in evidence
            if item.get("review_status") == "approved" and item.get("license_status") == "approved"
        }
        for citation in response.get("citations", []):
            citation_total += 1
            key = tuple(citation.get(name) for name in ("citation_id", "document_id", "chunk_id", "title", "source_url", "page"))
            citation_valid += key in evidence_keys

        safety_level = case.get("safety_level", "NORMAL")
        refusal_eligible = safety_level not in {"EMERGENCY", "CLINICAL_REVIEW", "UNIT_AMBIGUOUS"} and (
            bool(case.get("must_refuse")) or (not blocked and approved_count > 0)
        )
        actual_refusal = is_evidence_refusal(response)
        if refusal_eligible:
            expected_refusal = bool(case.get("must_refuse"))
            refusal_rows.append({
                "id": case["id"], "expected_refusal": expected_refusal,
                "actual_refusal": actual_refusal,
                "refusal_match": actual_refusal == expected_refusal,
                "status": response.get("status"),
                "citation_count": len(response.get("citations", [])),
            })
        rows.append({
            "id": case["id"], "expected_document_ids": sorted(expected_docs),
            "retrieved_document_ids": retrieved_ids, "retrieval_hits": hits,
            "blocked_until_approved": blocked, "retrieval_eligible": retrieval_eligible,
            "must_refuse": bool(case.get("must_refuse")), "actual_refusal": actual_refusal,
            "safety_level": safety_level, "response_status": response.get("status"),
            "citation_count": len(response.get("citations", [])),
            "retrieval_mode": search.get("retrieval_mode"), "degraded_reason": search.get("degraded_reason"),
        })

    blocked_count = sum(row["blocked_until_approved"] for row in rows)
    unmeasured = []
    if not approved_count:
        unmeasured.append("no approved KB documents")
    if not retrieval_case_count:
        unmeasured.append("no unblocked document-labeled retrieval cases")
    measured_refusal_rows = refusal_rows
    refusal_accuracy = (
        sum(row["refusal_match"] for row in refusal_rows) / len(refusal_rows)
        if refusal_rows else None
    )
    retrieval_measured = bool(retrieval_case_count and approved_count)
    report_status = "MEASURED" if retrieval_measured else "PARTIALLY_MEASURED" if measured_refusal_rows else "NOT_MEASURED"
    return {
        "status": report_status,
        "metric_scope": "Retrieval and citation metrics use approved, unblocked document-labeled questions; refusal metrics exclude safety-only outcomes.",
        "benchmark_scope": cases_data.get("scope"),
        "case_set": cases_path.name,
        "case_set_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest() if index_path.is_file() else None,
        "approved_document_count": approved_count,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        # A vector failure falls back to local search, so the modes show what was really measured.
        "retrieval_modes": sorted({str(row["retrieval_mode"]) for row in rows}),
        "degraded_reasons": sorted({row["degraded_reason"] for row in rows if row["degraded_reason"]}),
        "case_count": len(rows), "retrieval_case_count": retrieval_case_count,
        "blocked_until_approved_count": blocked_count,
        "refusal_case_count": len(measured_refusal_rows),
        "recall_at_5": retrieval_hits / expected_relevant if expected_relevant and approved_count else None,
        "precision_at_5": precision_sum / retrieval_case_count if retrieval_case_count and approved_count else None,
        "mrr": reciprocal_rank_sum / retrieval_case_count if retrieval_case_count and approved_count else None,
        "citation_accuracy": citation_valid / citation_total if citation_total and approved_count else None,
        "refusal_accuracy": refusal_accuracy,
        "not_measured_metrics": unmeasured,
        "not_measured_reason": "; ".join(unmeasured) if unmeasured else None,
        "results": rows, "refusal_results": measured_refusal_rows,
    }


def main() -> None:
    os.environ["DIACARE_WEB_SEARCH_ENABLED"] = "false"
    parser = argparse.ArgumentParser(description="Measure retrieval, structural citation, and refusal metrics.")
    parser.add_argument(
        "--cases", type=Path, default=ROOT / "evaluation" / "rag" / "gold_questions.json",
    )
    parser.add_argument("--index", type=Path, default=ROOT / "data" / "kb" / "index.json")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "evaluation" / "rag" / "evaluation_report.json",
    )
    args = parser.parse_args()
    cases_path = args.cases.resolve()
    cases_data = json.loads(cases_path.read_text(encoding="utf-8"))
    if "questions" in cases_data:
        report = evaluate_gold_questions(cases_path, args.index.resolve())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        # Saved reports retain readable Unicode; escape it only for terminals
        # whose Windows code page cannot encode Vietnamese text.
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return
    cases = cases_data.get("cases", [])
    kb = KnowledgeBase(args.index.resolve())
    approved_count = kb.approved_document_count
    rows = []
    retrieval_hits = 0
    expected_relevant = 0
    precision_sum = 0.0
    reciprocal_rank_sum = 0.0
    citation_total = 0
    citation_valid = 0
    retrieval_refusal_rows = []
    refusal_rows = []

    for case in cases:
        expected_ids = set(case.get("expected_chunk_ids", []))
        search = kb.search(case["query"], case.get("topic"), top_k=5)
        retrieved = search.get("evidence", [])[:5]
        retrieved_ids = [item.get("chunk_id") for item in retrieved]
        hits = len(expected_ids.intersection(retrieved_ids))
        expected_relevant += len(expected_ids)
        retrieval_hits += hits
        precision_sum += hits / 5
        rank = next((index + 1 for index, chunk_id in enumerate(retrieved_ids) if chunk_id in expected_ids), None)
        reciprocal_rank_sum += 1 / rank if rank else 0.0

        with patch(
            "app.agent.graph.search_kb",
            side_effect=lambda query, topic=None, top_k=5: kb.search(query, topic, top_k),
        ):
            response = run_agent(case["query"], None, None)
        evidence_keys = {
            tuple(item.get(key) for key in ("citation_id", "document_id", "chunk_id", "title", "source_url", "page"))
            for item in retrieved
            if item.get("review_status") == "approved" and item.get("license_status") == "approved"
        }
        for citation in response.get("citations", []):
            citation_total += 1
            key = tuple(citation.get(name) for name in ("citation_id", "document_id", "chunk_id", "title", "source_url", "page"))
            citation_valid += key in evidence_keys
        actual_refusal = is_evidence_refusal(response)
        row = {
            "id": case["id"], "expected_chunk_ids": sorted(expected_ids),
            "retrieved_chunk_ids": retrieved_ids, "retrieval_hits": hits,
            "actual_refusal": actual_refusal,
            "citation_count": len(response.get("citations", [])),
        }
        if approved_count:
            expect_refusal = bool(case["expect_refusal"])
            refusal_result = {
                "id": case["id"], "expected_refusal": expect_refusal,
                "actual_refusal": actual_refusal,
                "refusal_match": actual_refusal == expect_refusal,
            }
            row["expected_refusal"] = expect_refusal
            row["refusal_match"] = refusal_result["refusal_match"]
            retrieval_refusal_rows.append(refusal_result)
        rows.append(row)

    empty_corpus_refusal_cases = cases_data.get("refusal_cases", [])
    refusal_cases_skipped = len(empty_corpus_refusal_cases) if approved_count else 0
    refusal_cases_to_run = [] if approved_count else empty_corpus_refusal_cases
    for case in refusal_cases_to_run:
        with patch(
            "app.agent.graph.search_kb",
            side_effect=lambda query, topic=None, top_k=5: kb.search(query, topic, top_k),
        ):
            response = run_agent(case["query"], None, None)
        actual_refusal = is_evidence_refusal(response)
        expect_refusal = bool(case["expect_refusal"])
        refusal_rows.append({
            "id": case["id"], "expected_refusal": expect_refusal,
            "actual_refusal": actual_refusal,
            "refusal_match": actual_refusal == expect_refusal,
            "status": response.get("status"),
            "citation_count": len(response.get("citations", [])),
        })

    count = len(rows)
    retrieval_cases = sum(bool(case.get("expected_chunk_ids")) for case in cases)
    measured_refusal_rows = retrieval_refusal_rows + refusal_rows
    refusal_accuracy = (
        sum(row["refusal_match"] for row in measured_refusal_rows) / len(measured_refusal_rows)
        if measured_refusal_rows else None
    )
    retrieval_measured = bool(count and approved_count and retrieval_cases)
    unmeasured = []
    if not approved_count:
        unmeasured.append("no approved KB documents")
    if not retrieval_cases:
        unmeasured.append("no labeled retrieval cases")
    status = "MEASURED" if retrieval_measured else "PARTIALLY_MEASURED" if measured_refusal_rows else "NOT_MEASURED"
    report = {
        "status": status,
        "metric_scope": "Recall@5/MRR and structural citation validity require approved retrieval cases; refusal accuracy is measured separately on the supplied evidence-refusal cases",
        "benchmark_scope": cases_data.get("scope"),
        "case_set": cases_path.name,
        "case_set_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "index_sha256": hashlib.sha256(args.index.resolve().read_bytes()).hexdigest() if args.index.resolve().is_file() else None,
        "approved_document_count": approved_count,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": count + len(refusal_rows),
        "retrieval_case_count": count,
        "refusal_case_count": len(measured_refusal_rows),
        "empty_corpus_refusal_cases_skipped": refusal_cases_skipped,
        "recall_at_5": retrieval_hits / expected_relevant if expected_relevant and approved_count else None,
        "precision_at_5": precision_sum / retrieval_cases if retrieval_cases and approved_count else None,
        "mrr": reciprocal_rank_sum / retrieval_cases if retrieval_cases and approved_count else None,
        "citation_accuracy": citation_valid / citation_total if citation_total and approved_count else None,
        "refusal_accuracy": refusal_accuracy,
        "not_measured_metrics": unmeasured,
        "not_measured_reason": "; ".join(unmeasured) if unmeasured else None,
        "results": rows,
        "refusal_results": measured_refusal_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
