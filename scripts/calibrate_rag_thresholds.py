"""Report score separation between in-scope and out-of-scope queries, to choose refusal thresholds."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.embeddings import get_embedding_provider  # noqa: E402
from app.rag.reranker import reranker  # noqa: E402
from app.rag.retriever import KnowledgeBase  # noqa: E402
from app.rag.scope import is_in_kb_scope  # noqa: E402
from app.rag.vector_store import vector_store  # noqa: E402

OUT_OF_SCOPE = (
    "Giá cổ phiếu Apple hôm nay là bao nhiêu?",
    "Cách nấu phở bò ngon?",
    "How to fix a flat bicycle tire?",
    "Thủ đô của nước Pháp là gì?",
    "Lịch thi đấu bóng đá tuần này?",
    "Làm sao để học lập trình Python nhanh?",
    "Thời tiết Hà Nội ngày mai thế nào?",
    "Giải phương trình bậc hai như thế nào?",
    "What is the best smartphone to buy this year?",
    "Cách trồng hoa hồng trong chậu?",
    "Tỷ giá đô la hôm nay?",
    "Kinh nghiệm du lịch Đà Nẵng ba ngày?",
)


def in_scope_questions(path: Path) -> list[str]:
    cases = json.loads(path.read_text(encoding="utf-8"))["questions"]
    return [
        case["question"] for case in cases
        if case.get("safety_level") == "NORMAL" and not case.get("must_refuse")
    ]


def describe(values: list[float]) -> dict[str, float]:
    return {
        "min": round(min(values), 3),
        "median": round(statistics.median(values), 3),
        "max": round(max(values), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=ROOT / "tmp" / "kb_dry_run" / "dry_index.json")
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation" / "rag" / "gold_questions.json")
    parser.add_argument("--neural", action="store_true", help="Also score BGE-M3 dense hits and the reranker.")
    args = parser.parse_args()

    chunks = KnowledgeBase(args.index)._approved_chunks()
    groups = {"in_scope": in_scope_questions(args.cases), "out_of_scope": list(OUT_OF_SCOPE)}
    report: dict[str, dict] = {}
    for name, queries in groups.items():
        rows = []
        for query in queries:
            row = {"query": query, "in_kb_scope": is_in_kb_scope(query)}
            if args.neural:
                vector = get_embedding_provider().encode([query])[0]
                hits = vector_store.search(vector, topic=None, limit=15)
                known = {chunk["chunk_id"]: chunk for chunk in chunks}
                texts = [
                    known[hit["payload"]["chunk_id"]]["text"] for hit in hits
                    if (hit.get("payload") or {}).get("chunk_id") in known
                ]
                row["best_dense"] = round(max((float(hit.get("score", 0)) for hit in hits), default=0.0), 3)
                row["best_rerank"] = round(max(reranker.score(query, texts), default=-99.0), 3)
            rows.append(row)
        summary = {"in_kb_scope": sum(row["in_kb_scope"] for row in rows), "total": len(rows)}
        if args.neural:
            summary["best_dense"] = describe([row["best_dense"] for row in rows])
            summary["best_rerank"] = describe([row["best_rerank"] for row in rows])
        report[name] = {"summary": summary, "rows": rows}
    report["retrieval_env"] = {"DIACARE_RAG_MODE": os.getenv("DIACARE_RAG_MODE", "auto")}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
