"""생성물 이력 저장소 — 만든 PPT(대지분석 덱·종합읽기)를 목록으로 보관·재다운로드.

한 번 생성이 오래 걸리므로(외부 API 다수) 결과물을 버리지 않고 이력으로 남긴다.
- **영구 저장**: `GCS_CACHE_BUCKET` 설정 시 GCS 에 매니페스트(JSON)+blob(pptx) 저장 → 재시작·인스턴스 무관 유지.
- **로컬 폴백**: 미설정 시 OUT_DIR/history (Cloud Run 은 임시 FS라 인스턴스 수명 한정 — 정직).
매니페스트는 default_cache 재사용(백엔드 자동 일치). 개인 도구 수준 동시성이라 매니페스트 read-modify-write
경합은 감수(드문 경우 마지막 쓰기 우선). blob 은 backend 기록값 기준으로 읽어 매니페스트와 정합.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from app.config import OUT_DIR
from app.services.cache import default_cache, make_key

_MANIFEST_KEY = "gen_history_v1"
_MAX = 60  # 이력 상한 (초과분은 blob 삭제 후 매니페스트에서 제거)
_MEDIA = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _bucket() -> Optional[str]:
    return os.getenv("GCS_CACHE_BUCKET")


def _gcs_blob(gid: str):
    from google.cloud import storage  # 지연 임포트 (로컬 미설치 가능)

    return storage.Client().bucket(_bucket()).blob(f"history/{gid}.pptx")


def _local_path(gid: str):
    return OUT_DIR / "history" / f"{gid}.pptx"


def _entries() -> list:
    data = default_cache.get(_MANIFEST_KEY) or {}
    return list(data.get("items", []))


def _write_blob(gid: str, data: bytes) -> str:
    """blob 저장. 반환 backend('gcs'|'local'). GCS 실패 시 로컬 폴백."""
    if _bucket():
        try:
            _gcs_blob(gid).upload_from_string(data, content_type=_MEDIA)
            return "gcs"
        except Exception:  # noqa: BLE001 — GCS 실패해도 로컬로 남김(이력 유실 방지)
            pass
    p = _local_path(gid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return "local"


def _delete_blob(entry: dict) -> None:
    try:
        if entry.get("backend") == "gcs":
            _gcs_blob(entry["id"]).delete()
        else:
            _local_path(entry["id"]).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001 — 정리 실패는 비치명
        pass


def save(kind: str, title: str, params: dict, filename: str, data: bytes) -> dict:
    """생성물 1건 저장 + 매니페스트 등록. best-effort — 실패해도 예외 안 냄(생성은 이미 성공)."""
    created = datetime.now().isoformat(timespec="seconds")
    gid = make_key(kind, title, json.dumps(params, sort_keys=True, ensure_ascii=False), created)[:16]
    backend = _write_blob(gid, data)
    entry = {
        "id": gid, "kind": kind, "title": title, "params": params,
        "filename": filename, "created": created, "size": len(data), "backend": backend,
    }
    items = _entries()
    items.append(entry)
    if len(items) > _MAX:
        for old in items[:-_MAX]:
            _delete_blob(old)
        items = items[-_MAX:]
    default_cache.set(_MANIFEST_KEY, {"items": items})
    return entry


def list_entries() -> list:
    """최신순 이력 (파일 크기·backend 등 메타 포함, blob 은 미포함)."""
    return list(reversed(_entries()))


def read(gid: str) -> Optional[tuple]:
    """(bytes, filename) 또는 None(없음/만료)."""
    entry = next((e for e in _entries() if e.get("id") == gid), None)
    if not entry:
        return None
    fn = entry.get("filename") or f"{gid}.pptx"
    if entry.get("backend") == "gcs":
        try:
            return _gcs_blob(gid).download_as_bytes(), fn
        except Exception:  # noqa: BLE001
            return None
    p = _local_path(gid)
    if p.exists():
        return p.read_bytes(), fn
    return None
