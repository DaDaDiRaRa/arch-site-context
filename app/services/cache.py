"""캐시 추상화 (get/set 인터페이스).

로컬은 파일캐시. 나중에 GCS 등으로 교체 가능하도록 Cache 인터페이스로 추상화.
KOSIS 분당 호출 제한 대응 — 같은 (지역,항목,연도) 재호출 방지 (절대 원칙: 캐시 우선).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional, Protocol


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
        self.dir.mkdir(parents=True, exist_ok=True)
        self._path(key).write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )


class MemoryCache:
    """테스트용 인메모리 캐시."""

    def __init__(self) -> None:
        self._d: dict[str, dict] = {}

    def get(self, key: str) -> Optional[dict]:
        return self._d.get(key)

    def set(self, key: str, value: dict) -> None:
        self._d[key] = value


# 기본 로컬 캐시: out/kosis_cache
_DEFAULT_DIR = Path(__file__).resolve().parent.parent.parent / "out" / "kosis_cache"
default_cache = FileCache(_DEFAULT_DIR)
