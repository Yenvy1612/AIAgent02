"""Build a throwaway index from batch-1 candidates so the reviewer can read chunks before signing.

The real manifest and data/kb/index.json are never touched. Approval exists only in the temporary copy.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ingest_kb import MANIFEST, build_index  # noqa: E402

BATCH_1 = (
    "KB-01", "KB-01A", "KB-16", "KB-18", "KB-25", "KB-27", "KB-30A", "KB-30B",
    "KB-31", "KB-32", "KB-33", "KB-34",
)
OLD_AMENDED_WORDING = "insulin trộn không được khuyến cáo"


def write_dry_manifest(target: Path, codes: tuple[str, ...] = BATCH_1) -> None:
    with MANIFEST.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = [row for row in reader if row["source_code"] in codes]
    for row in rows:
        row["review_status"] = "approved"
        row["license_status"] = "approved"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize(chunks: list[dict]) -> dict:
    tokens = [chunk["token_count"] for chunk in chunks]
    normalized = [" ".join(chunk["text"].split()) for chunk in chunks]
    return {
        "chunks": len(chunks),
        "median_tokens": statistics.median(tokens) if tokens else None,
        "min_tokens": min(tokens, default=None),
        "max_tokens": max(tokens, default=None),
        "under_100_tokens": sum(value < 100 for value in tokens),
        "without_section": sum(not chunk.get("section") for chunk in chunks),
        "contents_like": sum(chunk["text"].count("....") >= 3 for chunk in chunks),
        "old_amended_wording": sum(OLD_AMENDED_WORDING in text for text in normalized),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=ROOT / "tmp" / "kb_dry_run")
    args = parser.parse_args()
    manifest = args.dir / "dry_manifest.csv"
    output = args.dir / "dry_index.json"
    write_dry_manifest(manifest)
    result = build_index(manifest, output)
    review = args.dir / "review_chunks.md"
    with review.open("w", encoding="utf-8") as handle:
        handle.write("# Chunk chạy thử để duyệt\n\nChưa được duyệt. Không dùng để trả lời.\n")
        for chunk in result["chunks"]:
            handle.write(
                f"\n## {chunk['chunk_id']}\n\n"
                f"Trang: {chunk['page']} | Mục: {chunk['section']} | Topic: {chunk['topic']} | "
                f"Sửa đổi: {chunk['amended']}\n\n{chunk['text']}\n"
            )
    print(json.dumps({
        **summarize(result["chunks"]),
        "blocked_sources": result["blocked_sources"],
        "pages_needing_manual_review": result["pages_needing_manual_review"],
    }, ensure_ascii=False, indent=2))
    print(f"Index: {output}\nReview file: {review}")


if __name__ == "__main__":
    main()
