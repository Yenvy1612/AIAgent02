from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.graph import run_agent  # noqa: E402
from app.llm.config import ALLOWED_MODELS, get_config  # noqa: E402
from app.rag.retriever import INDEX_PATH, KnowledgeBase, VECTOR_MODE  # noqa: E402

MODEL_PRICES = {
    "claude-opus-5-5": {"input": 4.0, "output": 20.0},
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},
}
ESTIMATED_INPUT_TOKENS = 6000
ESTIMATED_OUTPUT_TOKENS = 1500
OUTPUT_TOKEN_BUDGET = 16000


def _eligible_cases(gold: dict, suite: dict, approved_ids: set[str]) -> list[dict]:
    by_id = {case.get("id"): case for case in gold.get("questions", [])}
    result = []
    for spec in suite.get("cases", []):
        case = by_id.get(spec.get("gold_question_id"))
        if not case:
            continue
        expected = set(case.get("expected_document_ids", []))
        blocked = (
            (bool(expected) and not expected.issubset(approved_ids))
            or (bool(case.get("blocked_until_approved")) and not expected)
        )
        if (
            case.get("safety_level", "NORMAL") != "NORMAL"
            or case.get("must_refuse")
            or blocked
            or not expected
            or not expected.issubset(approved_ids)
        ):
            continue
        result.append({**case, "category": spec.get("category", "unspecified")})
    return result


def _estimate(models: list[str], case_count: int) -> dict[str, float]:
    expected = 0.0
    upper = 0.0
    for model in models:
        rates = MODEL_PRICES[model]
        calls = case_count
        expected += calls * (
            ESTIMATED_INPUT_TOKENS * rates["input"]
            + ESTIMATED_OUTPUT_TOKENS * rates["output"]
        ) / 1_000_000
        upper += calls * (
            ESTIMATED_INPUT_TOKENS * rates["input"]
            + OUTPUT_TOKEN_BUDGET * rates["output"]
        ) / 1_000_000
    return {"expected_usd": round(expected, 4), "output_budget_ceiling_usd": round(upper, 4)}


def _trace_step(response: dict, step_name: str) -> dict:
    return next((row for row in response.get("trace", []) if row.get("step") == step_name), {})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare deterministic and Claude answers on the curated, approved-source LLM suite."
    )
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation" / "llm" / "cases.json")
    parser.add_argument("--gold", type=Path, default=ROOT / "evaluation" / "rag" / "gold_questions.json")
    parser.add_argument("--index", type=Path, default=INDEX_PATH)
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "llm" / "latest_report.json")
    parser.add_argument("--models", nargs="+", default=["claude-opus-5-5", "claude-sonnet-5-5"])
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument(
        "--confirm-spend", action="store_true",
        help="Required to send real requests to Anthropic and incur API charges.",
    )
    args = parser.parse_args()
    unknown = set(args.models) - ALLOWED_MODELS
    if unknown:
        parser.error(f"Unsupported model(s): {', '.join(sorted(unknown))}")

    load_dotenv(ROOT / ".env", override=False)
    os.environ["DIACARE_WEB_SEARCH_ENABLED"] = "false"
    os.environ["DIACARE_LLM_MAX_TOKENS"] = str(OUTPUT_TOKEN_BUDGET)
    os.environ["DIACARE_LLM_EFFORT"] = "medium"
    suite = json.loads(args.cases.read_text(encoding="utf-8"))
    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    kb = KnowledgeBase(args.index)
    approved_ids = {chunk.get("document_id") for chunk in kb._approved_chunks()}
    cases = _eligible_cases(gold, suite, approved_ids)
    if args.max_cases is not None:
        cases = cases[:max(0, args.max_cases)]
    if not cases:
        raise SystemExit("No eligible cases remain after safety, approval, and gold-set filters.")

    retrieval = kb.health()
    estimate = _estimate(args.models, len(cases))
    preview = {
        "eligible_cases": len(cases),
        "models": args.models,
        "retrieval_modes": retrieval,
        "estimated_cost_usd": estimate,
        "estimate_basis": {
            "expected_input_tokens_per_call": ESTIMATED_INPUT_TOKENS,
            "expected_output_tokens_per_call": ESTIMATED_OUTPUT_TOKENS,
            "max_output_tokens_per_call": OUTPUT_TOKEN_BUDGET,
            "price_per_million_tokens_usd": MODEL_PRICES,
            "prices_reviewed_at": "2026-11-05",
        },
        "real_api_calls": len(cases) * len(args.models),
    }
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    if not args.confirm_spend:
        print("Preview only. Re-run with --confirm-spend to send API requests.")
        return
    if retrieval.get("retrieval_mode") != VECTOR_MODE:
        raise SystemExit(
            f"Refusing to evaluate: retrieval mode is {retrieval.get('retrieval_mode')!r}, expected {VECTOR_MODE!r}."
        )

    os.environ["DIACARE_LLM_ENABLED"] = "true"
    os.environ["DIACARE_LLM_DATA_LEVEL"] = "masked_question"
    first_model = args.models[0]
    os.environ["DIACARE_ANTHROPIC_MODEL"] = first_model
    config = get_config()
    if not config.configured:
        raise SystemExit(f"LLM configuration is invalid: {', '.join(config.errors) or 'disabled'}")

    deterministic_rows = []
    os.environ["DIACARE_LLM_ENABLED"] = "false"
    for case in cases:
        with patch(
            "app.agent.graph.search_kb",
            side_effect=lambda query, topic=None, top_k=5: kb.search(query, topic, top_k),
        ):
            response = run_agent(case["question"], None, None)
        deterministic_rows.append({"id": case["id"], "answer": response.get("answer", ""), "status": response.get("status")})

    model_reports = []
    for model in args.models:
        os.environ["DIACARE_LLM_ENABLED"] = "true"
        os.environ["DIACARE_ANTHROPIC_MODEL"] = model
        model_rows = []
        actual_cost = 0.0
        for case in cases:
            started = time.perf_counter()
            with patch(
                "app.agent.graph.search_kb",
                side_effect=lambda query, topic=None, top_k=5: kb.search(query, topic, top_k),
            ):
                response = run_agent(case["question"], None, None)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            llm_trace = _trace_step(response, "llm_composer")
            citations = response.get("citations", [])
            expected_ids = set(case.get("expected_document_ids", []))
            cited_ids = [citation.get("document_id") for citation in citations]
            served_model = llm_trace.get("model") or model
            rates = MODEL_PRICES.get(served_model, MODEL_PRICES[model])
            input_tokens = llm_trace.get("input_tokens") or 0
            output_tokens = llm_trace.get("output_tokens") or 0
            call_cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
            actual_cost += call_cost
            model_rows.append({
                "id": case["id"], "category": case.get("category"),
                "requested_model": model, "served_model": served_model,
                "status": response.get("status"), "answer_mode": response.get("answer_mode"),
                "reason": llm_trace.get("reason"), "answer": response.get("answer", ""),
                "expected_document_ids": sorted(expected_ids), "cited_document_ids": cited_ids,
                "expected_source_citation_match": bool(expected_ids.intersection(cited_ids)),
                "citation_count": len(citations), "latency_ms": elapsed_ms,
                "input_tokens": llm_trace.get("input_tokens"), "output_tokens": llm_trace.get("output_tokens"),
                "estimated_actual_cost_usd": round(call_cost, 6),
            })
        model_reports.append({
            "model": model,
            "llm_cited_count": sum(row["answer_mode"] == "llm_cited" for row in model_rows),
            "fallback_count": sum(row["answer_mode"] != "llm_cited" for row in model_rows),
            "expected_source_citation_rate": (
                sum(row["expected_source_citation_match"] for row in model_rows) / len(model_rows)
            ),
            "p95_latency_ms": sorted(row["latency_ms"] for row in model_rows)[max(0, math.ceil(len(model_rows) * 0.95) - 1)],
            "estimated_actual_cost_usd": round(actual_cost, 6),
            "results": model_rows,
        })

    report = {
        "status": "MEASURED_AUTOMATIC_ONLY",
        "manual_metrics_status": "NOT_MEASURED",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_set": str(args.cases.relative_to(ROOT)) if args.cases.is_relative_to(ROOT) else args.cases.name,
        "gold_set": str(args.gold.relative_to(ROOT)) if args.gold.is_relative_to(ROOT) else args.gold.name,
        "case_count": len(cases),
        "retrieval_modes": retrieval,
        "deterministic_baseline": deterministic_rows,
        "model_results": model_reports,
        "manual_review_required": suite.get("manual_review_required", []),
        "limitations": "Curated development set only; automatic citation-source matching is not a factuality or clinical-safety judgment.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "status": report["status"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
