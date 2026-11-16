"""Neural dense ranking: windowing, ranking with an injected encoder, and the optional API."""

import numpy as np
from fastapi.testclient import TestClient

from src.retrieval import dense


def _fake_encoder(texts):
    """Bag-of-letters vectors: deterministic, no model download."""
    vecs = np.zeros((len(texts), 26), dtype=np.float32)
    for i, t in enumerate(texts):
        for ch in t.lower():
            if "a" <= ch <= "z":
                vecs[i, ord(ch) - 97] += 1
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return vecs / norms


def test_windows_prefix_path_and_split_long_files():
    text = "\n".join(f"line {i}" for i in range(95))
    ws = dense.windows("src/a.py", text)
    assert len(ws) == 3 and all(w.startswith("src/a.py\n") for w in ws)


def test_rank_uses_best_window_and_is_deterministic(tmp_path):
    docs = {"cookies.js": "zzz cookie cookie parse", "math.js": "add subtract multiply"}
    idx = dense.DenseIndex(docs, encoder=_fake_encoder, cache_dir=tmp_path, cache_prefix="t")
    q = dense.embed_queries(["cookie parse"], _fake_encoder)[0]
    assert idx.rank_vec(q)[0] in docs
    assert idx.rank_vec(q) == idx.rank_vec(q)
    # second build hits the cache file instead of the encoder
    idx2 = dense.DenseIndex(docs, encoder=lambda _: (_ for _ in ()).throw(AssertionError("re-encoded")), cache_dir=tmp_path, cache_prefix="t")
    assert np.allclose(idx.vecs, idx2.vecs)


def test_empty_index_returns_paths():
    idx = dense.DenseIndex({}, encoder=_fake_encoder)
    assert idx.rank_vec(np.zeros(26, dtype=np.float32)) == []


def test_api_reports_unavailable_without_model(monkeypatch, tmp_path):
    import src.main as main

    monkeypatch.setattr(main.dense_retrieval, "available", lambda: False)
    monkeypatch.setenv("CODEAI_ANALYSIS_ROOT", str(tmp_path))
    client = TestClient(main.app)
    assert client.get("/dense/status").json()["available"] is False
    assert client.post("/dense/rank", json={"repository_path": str(tmp_path), "query": "x"}).status_code == 503


def test_api_index_then_rank(monkeypatch, tmp_path):
    import src.main as main

    (tmp_path / "cookies.js").write_text("cookie parse header", encoding="utf-8")
    (tmp_path / "math.js").write_text("add numbers", encoding="utf-8")
    monkeypatch.setattr(main.dense_retrieval, "available", lambda: True)
    monkeypatch.setattr(main.dense_retrieval, "default_encoder", _fake_encoder)
    monkeypatch.setenv("CODEAI_ANALYSIS_ROOT", str(tmp_path))
    client = TestClient(main.app)
    assert client.post("/dense/rank", json={"repository_path": str(tmp_path), "query": "cookie"}).status_code == 409
    main._build_dense_index(str(tmp_path.resolve()), tmp_path.resolve(), ["cookies.js", "math.js"])
    res = client.post("/dense/rank", json={"repository_path": str(tmp_path), "query": "cookie parse", "top_k": 1})
    assert res.status_code == 200 and res.json()["paths"] == ["cookies.js"]
    outside = client.post("/dense/index", json={"repository_path": "C:/Windows", "paths": []})
    assert outside.status_code in (400, 404)
