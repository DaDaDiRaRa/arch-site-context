"""캐시 추상화 (get/set 인터페이스).

로컬은 파일캐시. 나중에 GCS 등으로 교체 가능하도록 Cache 인터페이스로 추상화.
KOSIS 분당 호출 제한 대응 — 같은 (지역,항목,연도) 재호출 방지 (절대 원칙: 캐시 우선).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Protocol

from app.config import OUT_DIR


class Cache(Protocol):
    """키-값 캐시 인터페이스 (JSON 직렬화 가능 값)."""

    def get(self, key: str) -> Optional[dict]: ...
    def set(self, key: str, value: dict) -> None: ...


def make_key(*parts: object) -> str:
    """여러 식별자를 합쳐 안정적 캐시 키 생성."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class FileCache:
    """디렉터리 기반 파일 캐시 (키당 JSON 1파일)."""

    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str) -> Optional[dict]:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def set(self, key: str, value: dict) -> None:
        # 원자적 쓰기: temp 파일에 쓰고 os.replace 로 교체.
        # /board 등 병렬 브랜치가 같은 캐시 키를 동시에 write 해도 손상/절단 파일이 남지 않도록
        # (write_text 는 truncate 후 기록이라 concurrent reader 가 반쪽 파일을 읽을 수 있음).
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self._path(key)
        tmp = p.with_suffix(f".{os.getpid()}.{id(value)}.tmp")
        try:
            tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, p)  # 원자적 교체 (POSIX·Windows 모두)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


class MemoryCache:
    """테스트용 인메모리 캐시."""

    def __init__(self) -> None:
        self._d: dict[str, dict] = {}

    def get(self, key: str) -> Optional[dict]:
        return self._d.get(key)

    def set(self, key: str, value: dict) -> None:
        self._d[key] = value


class GCSCache:
    """GCS 버킷 기반 캐시 (Cloud Run 배포용). 인터페이스는 FileCache 와 동일.

    인증은 Application Default Credentials (Cloud Run 서비스 계정).
    google-cloud-storage 는 배포 이미지에만 설치 — 생성 시 지연 임포트.
    """

    def __init__(self, bucket_name: str, prefix: str = "kosis_cache") -> None:
        from google.cloud import storage  # 지연 임포트 (로컬은 미설치 가능)

        self._bucket = storage.Client().bucket(bucket_name)
        self._prefix = prefix.rstrip("/")

    def _blob(self, key: str):
        return self._bucket.blob(f"{self._prefix}/{key}.json")

    def get(self, key: str) -> Optional[dict]:
        # 없는 키(NotFound) 등 어떤 예외든 캐시 미스로 간주 → None (캐시는 보조).
        try:
            return json.loads(self._blob(key).download_as_text())
        except Exception:
            return None

    def set(self, key: str, value: dict) -> None:
        self._blob(key).upload_from_string(
            json.dumps(value, ensure_ascii=False), content_type="application/json"
        )


def _make_default_cache() -> Cache:
    """GCS_CACHE_BUCKET 있으면 GCS, 없으면 로컬 파일캐시 (캐시 우선 — 절대 원칙)."""
    bucket = os.getenv("GCS_CACHE_BUCKET")
    if bucket:
        return GCSCache(bucket)
    return FileCache(OUT_DIR / "kosis_cache")


# 기본 캐시 (kosis 등이 import). 환경에 따라 파일/GCS 자동 선택.
default_cache: Cache = _make_default_cache()
