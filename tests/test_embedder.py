import math

import pytest

from apps.matching.services import embedder


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_fake_embedder_is_normalized_and_deterministic():
    e = embedder.FakeEmbedder(384)
    v1, v2 = e.encode(["Python Django", "Python Django"])
    assert len(v1) == 384
    assert math.isclose(sum(x * x for x in v1), 1.0, rel_tol=1e-6)
    assert v1 == v2


def test_fake_embedder_similarity_reflects_overlap():
    e = embedder.FakeEmbedder(384)
    base, close, far = e.encode(
        ["développeur python django api", "python django backend", "comptable fiscalité audit"]
    )
    assert _cos(base, close) > _cos(base, far)


def test_fake_embedder_empty_text():
    assert embedder.FakeEmbedder(8).encode([""])[0][0] == 1.0


def test_get_embedder_backends(settings):
    settings.EMBEDDER_BACKEND = "fake"
    assert isinstance(embedder.get_embedder(), embedder.FakeEmbedder)
    settings.EMBEDDER_BACKEND = "sentence_transformers"
    st = embedder.get_embedder()
    assert isinstance(st, embedder.SentenceTransformerEmbedder)
    assert st._model is None  # chargement paresseux
    settings.EMBEDDER_BACKEND = "unknown"
    with pytest.raises(ValueError):
        embedder.get_embedder()
