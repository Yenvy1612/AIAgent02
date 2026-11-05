from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "kb_manifest" / "sources.csv"


def main() -> None:
    with MANIFEST.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    approved = [r for r in rows if r["review_status"] == "approved" and r["license_status"] == "approved"]
    print(f"Sources in manifest: {len(rows)}")
    print(f"Eligible for ingest: {len(approved)}")
    for row in rows:
        local = row.get("local_path", "").strip()
        exists = bool(local and (ROOT / local).is_file())
        state = "ELIGIBLE" if row in approved else "BLOCKED"
        path_state = "local file present" if exists else "no local file"
        print(f"{state:8} {row['source_code']:7} review={row['review_status']:<14} license={row['license_status']:<14} {path_state:16} {row['title']}")


if __name__ == "__main__":
    main()
