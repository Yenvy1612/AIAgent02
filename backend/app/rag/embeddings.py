from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


class BGEEmbeddingProvider:
    """Lazy BGE-M3 dense embeddings; the optional model is never loaded at import time."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("DIACARE_BGE_M3_MODEL", "BAAI/bge-m3")
        self._model: Any | None = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from FlagEmbedding import BGEM3FlagModel
            except ImportError as exc:
                raise RuntimeError("BGE-M3 dependencies are not installed; install backend/requirements-rag.txt") from exc
            use_fp16 = os.getenv("DIACARE_BGE_FP16", "false").strip().lower() in {"1", "true", "yes"}
            self._model = BGEM3FlagModel(self.model_name, use_fp16=use_fp16)
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        result = model.encode(
            texts,
            batch_size=int(os.getenv("DIACARE_BGE_BATCH_SIZE", "8")),
            max_length=512,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        vectors = result["dense_vecs"]
        return vectors.tolist() if hasattr(vectors, "tolist") else [list(row) for row in vectors]


@lru_cache(maxsize=1)
def get_embedding_provider() -> BGEEmbeddingProvider:
    return BGEEmbeddingProvider()
