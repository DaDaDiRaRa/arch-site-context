"""캐시 추상화 테스트 (P8) — 네트워크/실제 GCS 불필요.

FileCache 라운드트립, 환경 기반 선택, GCSCache 의 get/set 로직(가짜 버킷)을 검증.
"""

from __future__ import annotations

from app.services.cache import FileCache, GCSCache, MemoryCache, _make_default_cache, make_key


def test_make_key_stable() -> None:
    assert make_key("a", 1, None) == make_key("a", 1, None)
    assert make_key("a", 1) != make_key("a", 2)


def test_file_cache_roundtrip(tmp_path) -> None:
    c = FileCache(tmp_path)
    assert c.get("k") is None
    c.set("k", {"rows": [1, 2], "year": 2025})
    assert c.get("k") == {"rows": [1, 2], "year": 2025}


def test_memory_cache_roundtrip() -> None:
    c = MemoryCache()
    assert c.get("x") is None
    c.set("x", {"v": 1})
    assert c.get("x") == {"v": 1}


def test_default_cache_is_filecache_without_bucket(monkeypatch) -> None:
    monkeypatch.delenv("GCS_CACHE_BUCKET", raising=False)
    assert isinstance(_make_default_cache(), FileCache)


def test_gcs_cache_logic_with_fake_bucket() -> None:
    """GCSCache 의 get/set·키경로 로직을 가짜 버킷으로 검증 (실제 GCS 불필요)."""
    store: dict[str, str] = {}

    class FakeBlob:
        def __init__(self, name):
            self.name = name

        def download_as_text(self):
            if self.name not in store:
                raise KeyError(self.name)  # get 의 예외처리 → None
            return store[self.name]

        def upload_from_string(self, data, content_type=None):
            store[self.name] = data

    class FakeBucket:
        def blob(self, name):
            return FakeBlob(name)

    # __init__ 의 google 임포트를 우회하고 내부만 주입
    c = GCSCache.__new__(GCSCache)
    c._bucket = FakeBucket()
    c._prefix = "kosis_cache"

    assert c.get("missing") is None
    c.set("k1", {"rows": [1], "year": 2025})
    assert c.get("k1") == {"rows": [1], "year": 2025}
    assert "kosis_cache/k1.json" in store  # prefix 경로로 저장
