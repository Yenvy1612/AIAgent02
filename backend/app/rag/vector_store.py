from __future__ import annotations

import os
import re
from collections.abc import Sequence
from typing import Any

from psycopg.types.json import Jsonb

DEFAULT_TABLE = "kb_chunks"
DEFAULT_TIMEOUT_SECONDS = 2.0
_TABLE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}")
_POSTGRES_SCHEMES = ("postgresql://", "postgres://", "postgresql+psycopg://")


def _connection_url(url: str | None) -> str:
    url = (url or os.getenv("DIACARE_VECTOR_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not url.startswith(_POSTGRES_SCHEMES):
        return ""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in vector) + "]"


class PgVectorStore:
    """Dense vectors in PostgreSQL. Without a Postgres URL, retrieval stays in local mode."""

    def __init__(self, url: str | None = None, table: str | None = None):
        self._url = _connection_url(url)
        # Identifiers cannot be bound as SQL parameters, so the name must be checked before use.
        self.table = table or os.getenv("DIACARE_VECTOR_TABLE", DEFAULT_TABLE)
        if not _TABLE_RE.fullmatch(self.table):
            raise ValueError("DIACARE_VECTOR_TABLE must contain only letters, digits, and underscores")

    @property
    def configured(self) -> bool:
        return bool(self._url)

    def _connect(self, *, statement_timeout: bool = True):
        if not self.configured:
            raise RuntimeError("No PostgreSQL URL is configured for the vector store")
        import psycopg

        timeout = float(os.getenv("DIACARE_VECTOR_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        options = {"options": f"-c statement_timeout={int(timeout * 1000)}"} if statement_timeout else {}
        return psycopg.connect(self._url, connect_timeout=max(2, round(timeout)), **options)

    def _create_table(self, cursor: Any, vector_size: int) -> None:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.table} (
                chunk_id text PRIMARY KEY,
                review_status text NOT NULL,
                license_status text NOT NULL,
                is_active boolean NOT NULL,
                topic text,
                payload jsonb NOT NULL,
                embedding vector({int(vector_size)}) NOT NULL
            )
            """
        )

    def _insert(self, cursor: Any, chunks: list[dict[str, Any]], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunk and vector counts do not match")
        cursor.executemany(
            f"""
            INSERT INTO {self.table}
                (chunk_id, review_status, license_status, is_active, topic, payload, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
            ON CONFLICT (chunk_id) DO UPDATE SET
                review_status = EXCLUDED.review_status,
                license_status = EXCLUDED.license_status,
                is_active = EXCLUDED.is_active,
                topic = EXCLUDED.topic,
                payload = EXCLUDED.payload,
                embedding = EXCLUDED.embedding
            """,
            [
                (
                    chunk["chunk_id"], chunk.get("review_status"), chunk.get("license_status"),
                    bool(chunk.get("is_active", True)), chunk.get("topic"), Jsonb(chunk), _vector_literal(vector),
                )
                for chunk, vector in zip(chunks, vectors)
            ],
        )

    def ensure_collection(self, vector_size: int) -> None:
        with self._connect(statement_timeout=False) as connection, connection.cursor() as cursor:
            self._create_table(cursor, vector_size)

    def upsert(self, chunks: list[dict[str, Any]], vectors: Sequence[Sequence[float]]) -> None:
        with self._connect(statement_timeout=False) as connection, connection.cursor() as cursor:
            self._insert(cursor, chunks, vectors)

    def replace_all(self, chunks: list[dict[str, Any]], vectors: Sequence[Sequence[float]]) -> None:
        """Swap the whole table in one transaction, so a failed rebuild keeps the previous data."""
        if not vectors:
            raise ValueError("replace_all needs at least one vector")
        with self._connect(statement_timeout=False) as connection, connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {self.table}")
            self._create_table(cursor, len(vectors[0]))
            self._insert(cursor, chunks, vectors)

    def search(self, vector: Sequence[float], topic: str | None, limit: int = 15) -> list[dict[str, Any]]:
        literal = _vector_literal(vector)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT payload, 1 - (embedding <=> %s::vector) AS score
                FROM {self.table}
                WHERE review_status = 'approved' AND license_status = 'approved' AND is_active
                  AND (%s::text IS NULL OR topic = %s)
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (literal, topic, topic, literal, max(1, min(int(limit), 100))),
            )
            return [{"payload": payload, "score": float(score)} for payload, score in cursor.fetchall()]

    def health(self) -> dict[str, Any]:
        if not self.configured:
            return {"configured": False, "status": "disabled", "table": self.table}
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass(%s)", (self.table,))
                if cursor.fetchone()[0] is None:
                    return {"configured": True, "status": "table_missing", "table": self.table}
                cursor.execute(f"SELECT count(*) FROM {self.table}")
                return {"configured": True, "status": "ready", "chunk_count": cursor.fetchone()[0], "table": self.table}
        except Exception as exc:
            # The exception text can carry connection details, so only its type is reported.
            return {"configured": True, "status": "unavailable", "error": type(exc).__name__, "table": self.table}


vector_store = PgVectorStore()
