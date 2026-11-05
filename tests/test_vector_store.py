from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.retriever import LOCAL_MODE, VECTOR_MODE, KnowledgeBase  # noqa: E402
from app.rag.vector_store import PgVectorStore  # noqa: E402

UNREACHABLE = "postgresql+psycopg://diacare:s3cret-value@127.0.0.1:1/diacare"
TEST_URL = os.getenv("DIACARE_TEST_PG_URL")


def _chunk(chunk_id: str, topic: str = "diagnosis", **fields) -> dict:
    return {
        "chunk_id": chunk_id, "document_id": "KB-X", "title": "T", "topic": topic, "text": "Đái tháo đường.",
        "review_status": "approved", "license_status": "approved", "is_active": True, **fields,
    }


@pytest.mark.parametrize("url", ["sqlite:///./data/demo.sqlite3", ""])
def test_store_is_disabled_without_postgres(url, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DIACARE_VECTOR_DATABASE_URL", raising=False)
    store = PgVectorStore(url=url)
    assert store.configured is False
    assert store.health()["status"] == "disabled"


def test_store_reads_the_sqlalchemy_url_used_by_compose():
    assert PgVectorStore(url="postgresql+psycopg://u:p@db:5432/d")._url == "postgresql://u:p@db:5432/d"


@pytest.mark.parametrize("table", ["kb; DROP TABLE users", "kb-chunks", "1kb", 'kb"'])
def test_unsafe_table_names_are_rejected(table):
    with pytest.raises(ValueError):
        PgVectorStore(url=UNREACHABLE, table=table)


def test_health_on_an_unreachable_database_does_not_leak_the_url():
    health = PgVectorStore(url=UNREACHABLE).health()
    assert health["status"] == "unavailable"
    assert "s3cret" not in str(health) and "127.0.0.1" not in str(health)


@pytest.mark.parametrize("health, expected, reason", [
    ({"status": "ready", "chunk_count": 3}, VECTOR_MODE, None),
    ({"status": "ready", "chunk_count": 0}, LOCAL_MODE, "VECTOR_STORE_EMPTY"),
    ({"status": "table_missing"}, LOCAL_MODE, "VECTOR_STORE_TABLE_MISSING"),
    ({"status": "unavailable"}, LOCAL_MODE, "VECTOR_STORE_UNAVAILABLE"),
])
def test_readiness_follows_the_store_health(health, expected, reason, monkeypatch):
    monkeypatch.setenv("DIACARE_RAG_MODE", "auto")
    monkeypatch.setattr("app.rag.retriever.vector_store", PgVectorStore(url=UNREACHABLE))
    assert KnowledgeBase._retrieval_readiness(True, health) == (expected, reason)


def test_search_falls_back_to_local_when_the_database_is_down(tmp_path, monkeypatch):
    index = tmp_path / "index.json"
    index.write_text('{"chunks": [%s]}' % str(_chunk("KB-X-1")).replace("'", '"').replace("True", "true"), encoding="utf-8")
    monkeypatch.setenv("DIACARE_RAG_MODE", "auto")
    monkeypatch.setattr("app.rag.retriever.vector_store", PgVectorStore(url=UNREACHABLE))
    monkeypatch.setattr("app.rag.retriever.get_embedding_provider", lambda: type("E", (), {"encode": lambda self, texts: [[0.0]]})())
    result = KnowledgeBase(index).search("Đái tháo đường là gì?")
    assert result["retrieval_mode"] == LOCAL_MODE
    assert result["degraded_reason"].startswith("VECTOR_PIPELINE_UNAVAILABLE")


@pytest.fixture
def real_store():
    if not TEST_URL:
        pytest.skip("Set DIACARE_TEST_PG_URL to run against a real PostgreSQL with pgvector")
    store = PgVectorStore(url=TEST_URL, table="kb_chunks_pytest")
    yield store
    with store._connect() as connection:
        connection.execute("DROP TABLE IF EXISTS kb_chunks_pytest")


def test_real_search_filters_and_orders_by_similarity(real_store):
    real_store.replace_all(
        [
            _chunk("near"), _chunk("far"), _chunk("other-topic", topic="nutrition"),
            _chunk("candidate", review_status="candidate"), _chunk("unlicensed", license_status="unknown"),
            _chunk("inactive", is_active=False),
        ],
        [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [1.0, 0.0], [1.0, 0.0]],
    )
    hits = real_store.search([1.0, 0.0], topic="diagnosis")
    assert [hit["payload"]["chunk_id"] for hit in hits] == ["near", "far"]
    assert hits[0]["score"] == pytest.approx(1.0)
    assert hits[1]["score"] == pytest.approx(0.0)
    assert {hit["payload"]["chunk_id"] for hit in real_store.search([1.0, 0.0], topic=None)} == {"near", "far", "other-topic"}
    assert real_store.health() == {"configured": True, "status": "ready", "chunk_count": 6, "table": "kb_chunks_pytest"}


def test_real_failed_rebuild_keeps_the_previous_rows(real_store):
    real_store.replace_all([_chunk("old")], [[1.0, 0.0]])
    # The second vector has the wrong size, so the insert fails after the table was dropped and recreated.
    with pytest.raises(Exception):
        real_store.replace_all([_chunk("new-1"), _chunk("new-2")], [[1.0, 0.0], [1.0, 0.0, 0.0]])
    assert [hit["payload"]["chunk_id"] for hit in real_store.search([1.0, 0.0], topic=None)] == ["old"]
