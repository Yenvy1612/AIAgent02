from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.embeddings import get_embedding_provider  # noqa: E402
from app.rag.vector_store import PgVectorStore  # noqa: E402


def eligible_chunks(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        chunk for chunk in raw.get("chunks", [])
        if chunk.get("review_status") == "approved"
        and chunk.get("license_status") == "approved"
        and chunk.get("is_active", True)
        and chunk.get("chunk_id")
        and chunk.get("text")
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Index already approved DiaCare KB chunks into pgvector with BGE-M3.")
    parser.add_argument("--index", type=Path, default=ROOT / "data" / "kb" / "index.json")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    chunks = eligible_chunks(args.index)
    if not chunks:
        raise SystemExit("No approved and licensed KB chunks found; nothing was indexed.")
    store = PgVectorStore()
    if not store.configured:
        raise SystemExit("Set DIACARE_VECTOR_DATABASE_URL or a PostgreSQL DATABASE_URL before indexing.")
    embedder = get_embedding_provider()
    first = embedder.encode([chunks[0]["text"]])[0]
    store.ensure_collection(len(first))
    store.upsert([chunks[0]], [first])
    print(f"Indexed 1/{len(chunks)} chunks into {store.table}")

    batch_size = max(1, args.batch_size)
    for start in range(1, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        vectors = embedder.encode([chunk["text"] for chunk in batch])
        store.upsert(batch, vectors)
        print(f"Indexed {min(start + len(batch), len(chunks))}/{len(chunks)} chunks into {store.table}")


if __name__ == "__main__":
    main()
