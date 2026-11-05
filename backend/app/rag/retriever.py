from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR
from app.rag.embeddings import get_embedding_provider
from app.rag.reranker import reranker
from app.rag.scope import is_in_kb_scope
from app.rag.vector_store import vector_store


INDEX_PATH = Path(DATA_DIR) / "kb" / "index.json"
LOCAL_MODE = "local-hybrid-tfidf-bm25"
VECTOR_MODE = "pgvector-bge-m3-bm25-rrf-bge-reranker"
# Raw reranker logit. English sources score low against Vietnamese questions, and a threshold of 0 refused
# most valid ones. -6 keeps every labeled case in the gold set; is_in_kb_scope handles unrelated queries.
DEFAULT_MIN_RERANK_SCORE = -6.0


def _normalize(text: str) -> str:
    text = text.lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def _terms(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalize(text))


def _char_ngrams(text: str, n: int = 3) -> Counter[str]:
    compact = " " + _normalize(text) + " "
    return Counter(compact[i:i + n] for i in range(max(0, len(compact) - n + 1)))


def _cosine(left: Counter[str], right: Counter[str], document_frequency: Counter[str], count: int) -> float:
    if not left or not right:
        return 0.0

    def weighted(counter: Counter[str]) -> dict[str, float]:
        return {
            token: (1 + math.log(freq)) * (math.log(1 + (count + 1) / (document_frequency[token] + 1)) + 1)
            for token, freq in counter.items()
        }

    a, b = weighted(left), weighted(right)
    dot = sum(value * b.get(token, 0.0) for token, value in a.items())
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


class KnowledgeBase:
    def __init__(self, index_path: Path = INDEX_PATH):
        self.index_path = index_path

    def _approved_chunks(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [
            row for row in raw.get("chunks", [])
            if row.get("review_status") == "approved" and row.get("license_status") == "approved"
            and row.get("is_active", True)
        ]

    @property
    def approved_document_count(self) -> int:
        return len({chunk.get("document_id") for chunk in self._approved_chunks()})

    @property
    def retrieval_mode(self) -> str:
        optional_models_installed = importlib.util.find_spec("FlagEmbedding") is not None
        store_health = vector_store.health()
        return self._retrieval_readiness(optional_models_installed, store_health)[0]

    @staticmethod
    def _retrieval_readiness(
        optional_models_installed: bool, store_health: dict[str, Any],
    ) -> tuple[str, str | None]:
        configured = os.getenv("DIACARE_RAG_MODE", "auto").strip().lower()
        if configured == "local":
            return LOCAL_MODE, None
        if configured not in {"auto", "vector"}:
            return LOCAL_MODE, "RAG_MODE_FORCED_LOCAL"
        if not vector_store.configured:
            return LOCAL_MODE, "VECTOR_STORE_NOT_CONFIGURED"
        if not optional_models_installed:
            return LOCAL_MODE, "BGE_MODELS_NOT_INSTALLED"
        if store_health.get("status") != "ready":
            return LOCAL_MODE, f"VECTOR_STORE_{str(store_health.get('status', 'unavailable')).upper()}"
        if not store_health.get("chunk_count"):
            return LOCAL_MODE, "VECTOR_STORE_EMPTY"
        return VECTOR_MODE, None

    def health(self) -> dict[str, Any]:
        optional_models_installed = importlib.util.find_spec("FlagEmbedding") is not None
        store_health = vector_store.health()
        retrieval_mode, retrieval_fallback_reason = self._retrieval_readiness(
            optional_models_installed, store_health,
        )
        return {
            "approved_document_count": self.approved_document_count,
            "retrieval_mode": retrieval_mode,
            "retrieval_fallback_reason": retrieval_fallback_reason,
            "vector_store": store_health,
            "bge_models": {
                "package_installed": optional_models_installed,
                "embedding_model": os.getenv("DIACARE_BGE_M3_MODEL", "BAAI/bge-m3"),
                "reranker_model": os.getenv("DIACARE_BGE_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
            },
        }

    def _rank_local(self, query: str, chunks: list[dict[str, Any]]) -> tuple[list[int], list[float], list[float]]:
        query_terms = _terms(query)
        docs = [_terms(c.get("text", "")) for c in chunks]
        avg_len = sum(map(len, docs)) / max(1, len(docs))
        doc_freq: Counter[str] = Counter()
        for terms in docs:
            doc_freq.update(set(terms))
        query_grams = _char_ngrams(query)
        gram_docs = [_char_ngrams(c.get("text", "")) for c in chunks]
        gram_df: Counter[str] = Counter()
        for grams in gram_docs:
            gram_df.update(grams.keys())
        bm25: list[float] = []
        for terms in docs:
            counts = Counter(terms)
            score = 0.0
            for term in query_terms:
                if term not in counts:
                    continue
                idf = math.log(1 + (len(docs) - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                freq = counts[term]
                denom = freq + 1.2 * (1 - 0.75 + 0.75 * len(terms) / max(1, avg_len))
                score += idf * freq * 2.2 / denom
            bm25.append(score)
        char_scores = [_cosine(query_grams, grams, gram_df, len(chunks)) for grams in gram_docs]
        return bm25, char_scores, docs

    @staticmethod
    def _insufficient(query: str, topic: str | None, retrieval_mode: str, reason: str | None = None) -> dict[str, Any]:
        result = {
            "status": "INSUFFICIENT_EVIDENCE", "query": query, "topic": topic,
            "retrieval_mode": retrieval_mode, "evidence": [],
            "message": "Không đủ thông tin đáng tin cậy đã được duyệt trong Knowledge Base.",
        }
        if reason:
            result["degraded_reason"] = reason
        return result

    @staticmethod
    def _evidence(chunk: dict[str, Any], rank: int, score: float, **extra: Any) -> dict[str, Any]:
        item = {
            "citation_id": f"C{rank}", "document_id": chunk["document_id"],
            "chunk_id": chunk["chunk_id"], "title": chunk["title"],
            "source_url": chunk.get("source_url"), "page": chunk.get("page"),
            "topic": chunk.get("topic"), "excerpt": chunk["text"],
            "review_status": chunk["review_status"], "license_status": chunk["license_status"],
            "retrieval_score": round(score, 6),
            "document_version": chunk.get("document_version"),
            "section": chunk.get("section"), "language": chunk.get("language"),
            "population": chunk.get("population"), "content_hash": chunk.get("content_hash"),
            "is_active": chunk.get("is_active", True),
            "supersedes": chunk.get("supersedes", []),
            "amended_by": chunk.get("amended_by", []),
            "amended": chunk.get("amended", False),
            "amended_section": chunk.get("amended_section"),
        }
        item.update(extra)
        return item

    def _local_search(
        self, query: str, topic: str | None, top_k: int, chunks: list[dict[str, Any]],
        reason: str | None = None,
    ) -> dict[str, Any]:
        # Local scores are relative to the best chunk, so an unrelated query still tops out near 1.
        if not is_in_kb_scope(query):
            return self._insufficient(query, topic, LOCAL_MODE, reason or "QUERY_OUT_OF_KB_SCOPE")
        bm25, char_scores, _ = self._rank_local(query, chunks)
        if not chunks or ((max(bm25) if bm25 else 0.0) == 0.0 and (max(char_scores) if char_scores else 0.0) < 0.08):
            return self._insufficient(query, topic, LOCAL_MODE, reason)
        max_bm = max(bm25) or 1
        max_char = max(char_scores) or 1
        scores = [0.52 * bm25[i] / max_bm + 0.48 * char_scores[i] / max_char for i in range(len(chunks))]
        ranked = [i for i in sorted(range(len(chunks)), key=lambda idx: scores[idx], reverse=True) if scores[i] >= 0.08][:top_k]
        if not ranked:
            return self._insufficient(query, topic, LOCAL_MODE, reason)
        evidence = [self._evidence(chunks[i], rank, scores[i]) for rank, i in enumerate(ranked, 1)]
        result = {
            "status": "OK", "query": query, "topic": topic,
            "retrieval_mode": LOCAL_MODE, "evidence": evidence,
        }
        if reason:
            result["degraded_reason"] = reason
        return result

    def _vector_search(
        self, query: str, topic: str | None, top_k: int, chunks: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        # Rerank scores of in-scope and out-of-scope queries overlap, so the score alone cannot refuse these.
        if not is_in_kb_scope(query):
            return self._insufficient(query, topic, VECTOR_MODE, "QUERY_OUT_OF_KB_SCOPE")
        vectors = get_embedding_provider().encode([query])
        hits = vector_store.search(vectors[0], topic=topic, limit=15)
        by_chunk = {chunk.get("chunk_id"): (i, chunk) for i, chunk in enumerate(chunks)}
        dense_hits: list[tuple[int, dict[str, Any], float]] = []
        for hit in hits:
            payload = hit.get("payload") or {}
            found = by_chunk.get(payload.get("chunk_id"))
            if not found:
                continue
            index, chunk = found
            dense_hits.append((index, chunk, float(hit.get("score", 0.0))))
        if not dense_hits:
            return None

        bm25, char_scores, _ = self._rank_local(query, chunks)
        max_bm = max(bm25) if bm25 else 0.0
        max_char = max(char_scores) if char_scores else 0.0
        lexical_order = sorted(range(len(chunks)), key=lambda i: (bm25[i], char_scores[i]), reverse=True)
        lexical_ids = [idx for idx in lexical_order[:15] if bm25[idx] > 0 or char_scores[idx] >= 0.08]
        min_dense = float(os.getenv("DIACARE_RAG_MIN_DENSE_SCORE", "0.25"))
        dense_hits = [hit for hit in dense_hits if hit[2] >= min_dense]
        if not dense_hits and (not lexical_ids or (max_bm == 0.0 and max_char < 0.08)):
            return self._insufficient(query, topic, VECTOR_MODE)

        dense_order = [hit[0] for hit in dense_hits]
        dense_score = {idx: score for idx, _, score in dense_hits}
        dense_rank = {idx: rank + 1 for rank, idx in enumerate(dense_order)}
        lexical_rank = {idx: rank + 1 for rank, idx in enumerate(lexical_ids)}
        candidates = set(dense_order) | set(lexical_ids)
        fused = {}
        for idx in candidates:
            dense_contribution = 1 / (60 + dense_rank[idx]) if idx in dense_rank else 0.0
            lexical_contribution = 1 / (60 + lexical_rank[idx]) if idx in lexical_rank else 0.0
            fused[idx] = dense_contribution + lexical_contribution
        candidate_ids = sorted(candidates, key=lambda idx: fused[idx], reverse=True)[:max(top_k * 3, top_k)]
        rerank_scores = reranker.score(query, [chunks[idx]["text"] for idx in candidate_ids])
        min_rerank = float(os.getenv("DIACARE_RAG_MIN_RERANK_SCORE", str(DEFAULT_MIN_RERANK_SCORE)))
        ordered_positions = sorted(
            (pos for pos in range(len(candidate_ids)) if rerank_scores[pos] >= min_rerank),
            key=lambda pos: rerank_scores[pos], reverse=True,
        )
        evidence = []
        for position in ordered_positions[:top_k]:
            idx = candidate_ids[position]
            evidence.append(self._evidence(
                chunks[idx], len(evidence) + 1, fused[idx],
                dense_score=round(dense_score[idx], 6) if idx in dense_score else None,
                rerank_score=round(rerank_scores[position], 6),
            ))
        if not evidence:
            return self._insufficient(query, topic, VECTOR_MODE)
        return {"status": "OK", "query": query, "topic": topic, "retrieval_mode": VECTOR_MODE, "evidence": evidence}

    def search(self, query: str, topic: str | None = None, top_k: int = 5) -> dict[str, Any]:
        chunks = self._approved_chunks()
        if topic:
            chunks = [chunk for chunk in chunks if chunk.get("topic") == topic]
        if not chunks:
            return self._insufficient(query, topic, self.retrieval_mode)
        top_k = max(1, min(int(top_k), 5))
        mode = os.getenv("DIACARE_RAG_MODE", "auto").strip().lower()
        if vector_store.configured and mode in {"auto", "vector"}:
            try:
                result = self._vector_search(query, topic, top_k, chunks)
                if result is not None:
                    return result
                return self._local_search(query, topic, top_k, chunks, "VECTOR_STORE_EMPTY_OR_INDEX_OUT_OF_DATE")
            except Exception as exc:
                return self._local_search(query, topic, top_k, chunks, f"VECTOR_PIPELINE_UNAVAILABLE:{type(exc).__name__}")
        return self._local_search(query, topic, top_k, chunks)


knowledge_base = KnowledgeBase()
