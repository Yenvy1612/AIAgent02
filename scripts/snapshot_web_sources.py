from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.loader import load_web_html  # noqa: E402

MANIFEST = ROOT / "kb_manifest" / "sources.csv"
CANDIDATES = ROOT / "data" / "kb" / "candidates"
SNAPSHOT_CODES = {"KB-25", "KB-27", "KB-30A", "KB-30B"}


def _fetch(url: str) -> str:
    import trafilatura
    html = trafilatura.fetch_url(url)
    if not html:
        raise RuntimeError("Trafilatura returned no page content")
    return html


def snapshot_sources(
    manifest_path: Path = MANIFEST,
    candidates_dir: Path = CANDIDATES,
    *,
    accessed_on: date | None = None,
    fetch: Callable[[str], str] = _fetch,
    root_dir: Path = ROOT,
) -> dict:
    accessed_on = accessed_on or date.today()
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    saved: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for row in rows:
        code = row.get("source_code", "")
        if code not in SNAPSHOT_CODES:
            continue
        if row.get("license_status") != "approved":
            skipped.append({"source_code": code, "reason": "license_status is not approved"})
            continue
        url = (row.get("source_url") or "").strip()
        if not url:
            skipped.append({"source_code": code, "reason": "source_url is missing"})
            continue
        try:
            markdown = load_web_html(fetch(url), url)
            if not markdown.strip():
                raise RuntimeError("Trafilatura extracted no text")
            body_sha = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
            filename = f"{code}_{accessed_on.isoformat()}.md"
            target = candidates_dir / filename
            front_matter = "\n".join((
                "---",
                f"source_code: {code}",
                f"url: {json.dumps(url, ensure_ascii=False)}",
                f"accessed_date: {accessed_on.isoformat()}",
                f"content_sha256: {body_sha}",
                f"organization: {json.dumps(row.get('organization', ''), ensure_ascii=False)}",
                "---",
                "",
            ))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(front_matter + markdown.rstrip() + "\n", encoding="utf-8")
            file_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            row["local_path"] = target.relative_to(root_dir).as_posix() if target.is_relative_to(root_dir) else str(target)
            row["content_sha256"] = file_sha
            saved.append({"source_code": code, "local_path": row["local_path"], "content_sha256": file_sha})
        except Exception as exc:
            skipped.append({"source_code": code, "reason": f"snapshot failed ({type(exc).__name__})"})

    temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(manifest_path)
    return {"accessed_date": accessed_on.isoformat(), "saved": saved, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot only the four license-reviewed P0 CDC/WHO pages.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    args = parser.parse_args()
    result = snapshot_sources(args.manifest.resolve(), args.candidates.resolve())
    for item in result["saved"]:
        print(f"SNAPSHOT {item['source_code']}: {item['local_path']} sha256={item['content_sha256']}")
    for item in result["skipped"]:
        print(f"SKIPPED {item['source_code']}: {item['reason']}")


if __name__ == "__main__":
    main()
