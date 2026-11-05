from __future__ import annotations

import os
from typing import Any


class BGEReranker:
    """Lazy multilingual cross-encoder reranker from FlagEmbedding."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv(
            "DIACARE_BGE_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"
        )
        self._model: Any | None = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from FlagEmbedding import FlagReranker
            except ImportError as exc:
                raise RuntimeError("BGE reranker dependencies are not installed; install backend/requirements-rag.txt") from exc
            # Separate from DIACARE_BGE_FP16: half precision made reranking about five times slower on a GTX 1650.
            use_fp16 = os.getenv("DIACARE_BGE_RERANK_FP16", "false").strip().lower() in {"1", "true", "yes"}
            self._model = FlagReranker(self.model_name, use_fp16=use_fp16)
        return self._model

    def score(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        pairs = [[query, document] for document in documents]
        # FlagEmbedding runs one extra probe pass over the first batch, so a large batch is scored twice.
        batch_size = int(os.getenv("DIACARE_BGE_RERANK_BATCH_SIZE", "4"))
        raw = self._load().compute_score(pairs, batch_size=batch_size)
        if isinstance(raw, (int, float)):
            return [float(raw)]
        return [float(value) for value in raw]


reranker = BGEReranker()
