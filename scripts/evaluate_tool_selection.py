from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.graph import run_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure exact tool selection on a reviewed JSON case set.")
    parser.add_argument(
        "--cases", type=Path, default=ROOT / "evaluation" / "agent" / "tool_selection_cases.json",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "evaluation" / "agent" / "tool_selection_report.json",
    )
    args = parser.parse_args()
    cases_path = args.cases.resolve()
    cases = json.loads(cases_path.read_text(encoding="utf-8")).get("cases", [])
    results = []
    for case in cases:
        # Exercise the complete answer graph. A missing DB keeps this check
        # self-contained; tool failures are caught and should still be traced.
        response = run_agent(case["message"], None, None)
        actual = [call["tool"] for call in response.get("tool_calls", [])]
        expected = case["expected_tools"]
        trace = response.get("trace", [])
        results.append({
            "id": case["id"], "expected_tools": expected, "actual_tools": actual,
            "exact_match": actual == expected, "call_count": len(actual),
            "within_cap": len(actual) <= 5,
            "answer_present": bool(response.get("answer")),
            "trace_step_count": len(trace), "has_trace": bool(trace),
        })
    count = len(results)
    matched = sum(item["exact_match"] for item in results)
    answered = sum(item["answer_present"] for item in results)
    traced_answers = sum(item["answer_present"] and item["has_trace"] for item in results)
    report = {
        "status": "MEASURED" if count else "NOT_MEASURED",
        "metric_scope": "full agent-graph execution on curated routes; DB omitted so database-dependent tools may return degraded responses",
        "case_set": cases_path.name,
        "case_set_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": count,
        "tool_selection_accuracy": matched / count if count else None,
        "exact_matches": matched,
        "all_within_five_tool_cap": all(item["within_cap"] for item in results) if count else None,
        "answers_with_trace": traced_answers,
        "answer_count": answered,
        "all_answers_have_trace": traced_answers == answered if answered else None,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
