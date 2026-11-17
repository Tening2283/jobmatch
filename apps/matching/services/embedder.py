"""Abstraction des modèles d'embeddings."""

from __future__ import annotations

import hashlib
import math
import re
import threading
from functools import lru_cache
from typing import Protocol

from django.conf import settings


class Embedder(Protocol):
    dimensions: int

    def encode(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """Modèle multilingue local, chargé paresseusement une fois par process."""

    def __init__(self, model_name: str, dimensions: int):
        self.model_name = model_name
        self.dimensions = dimensions
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - modèle lourd
        vectors = self._load().encode(
            texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False
        )
        return [v.tolist() for v in vectors]


class FakeEmbedder:
    """Embedder déterministe par hachage de tokens (tests/CI, sans modèle).

    Deux textes partageant des mots ont une similarité cosinus > 0, ce qui permet
    de tester le classement de manière réaliste.
    """

    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def _encode_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        for token in re.findall(r"\w+", text.lower()):
            if len(token) < 2:
                continue
            digest = hashlib.md5(token.encode(), usedforsecurity=False).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimensions
            vec[idx] += 1.0 if digest[4] % 2 else -1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            vec[0], norm = 1.0, 1.0
        return [x / norm for x in vec]

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._encode_one(t) for t in texts]


@lru_cache(maxsize=4)
def _build(backend: str, model_name: str, dimensions: int) -> Embedder:
    if backend == "fake":
        return FakeEmbedder(dimensions)
    if backend == "sentence_transformers":
        return SentenceTransformerEmbedder(model_name, dimensions)
    raise ValueError(f"EMBEDDER_BACKEND inconnu : {backend}")


def get_embedder() -> Embedder:
    return _build(
        settings.EMBEDDER_BACKEND, settings.EMBEDDING_MODEL_NAME, settings.EMBEDDING_DIMENSIONS
    )


def embed_text(text: str) -> list[float]:
    return get_embedder().encode([text])[0]
