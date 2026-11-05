from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.rag.embeddings import get_embedding_provider  # noqa: E402
from app.rag.vector_store import PgVectorStore  # noqa: E402
from index_vectors import eligible_chunks  # noqa: E402
from ingest_kb import build_index  # noqa: E402


def rebuild(index_path: Path) -> int:
    result = build_index(output_path=index_path)
    chunks = eligible_chunks(index_path)
    if not chunks:
        print("No approved chunks; the vector table was left untouched.")
        return 0

    store = PgVectorStore()
    if not store.configured:
        raise RuntimeError("Approved chunks exist, but no PostgreSQL URL is configured for pgvector.")

    embedder = get_embedding_provider()
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), 16):
        vectors.extend(embedder.encode([chunk["text"] for chunk in chunks[start:start + 16]]))

    store.replace_all(chunks, vectors)
    print(f"Indexed {len(chunks)} chunks into {store.table}")
    return len(chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the approved local KB index and the pgvector table.")
    parser.add_argument("--index", type=Path, default=ROOT / "data" / "kb" / "index.json")
    args = parser.parse_args()
    count = rebuild(args.index.resolve())
    print(f"KB rebuild complete: {count} approved chunks")


if __name__ == "__main__":
    main()
