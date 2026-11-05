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
    parser = argparse.ArgumentParser(description="Measure curated glucose-unit and clarification cases.")
    parser.add_argument(
        "--cases", type=Path, default=ROOT / "evaluation" / "units" / "unit_cases.json",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "evaluation" / "units" / "unit_report.json",
    )
    args = parser.parse_args()
    cases_path = args.cases.resolve()
    case_set = json.loads(cases_path.read_text(encoding="utf-8"))
    results = []
    for case in case_set.get("cases", []):
        response = run_agent(case["message"], None, None)
        answer = response.get("answer", "")
        missing = [fragment for fragment in case["must_contain"] if fragment not in answer]
        passed = not missing and bool(response.get("trace")) and len(response.get("tool_calls", [])) <= 5
        results.append({
            "id": case["id"], "status": response.get("status"),
            "expected_fragments": case["must_contain"], "missing_fragments": missing,
            "trace_present": bool(response.get("trace")),
            "tool_count": len(response.get("tool_calls", [])), "passed": passed,
        })
    count = len(results)
    passed = sum(item["passed"] for item in results)
    report = {
        "status": "MEASURED" if count else "NOT_MEASURED",
        "scope": case_set.get("scope"), "case_set": cases_path.name,
        "case_set_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": count, "passed_count": passed,
        "unit_case_pass_rate": passed / count if count else None,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
