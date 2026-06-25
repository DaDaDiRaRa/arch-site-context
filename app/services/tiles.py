"""웹메르카토르 타일 수학 + 배경지도(BASEMAPS) 타일 합성.

입력 좌표는 WGS84. 타일은 표준 슬리피맵(웹메르카토르) 스킴.
배경은 BASEMAPS 로 추상화 — vworld(위성 jpeg) 구현, kakao(스카이뷰)는 자리만.
"""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
from typing import Callable, Optional

import httpx
from PIL import Image

TILE_SIZE = 256
# 적도 기준 m/px (zoom 0). 위도 보정은 cos(lat).
_EQUATOR_MPP_Z0 = 2 * math.pi * 6378137.0 / TILE_SIZE  # 156543.0339...


# ── 배경지도 추상화 ──────────────────────────────────────────
def _vworld_url(z: int, x: int, y: int) -> str:
    key = os.getenv("VWORLD_KEY", "")
    # 경로 순서 주의: /{z}/{y}/{x}.jpeg
    return f"https://api.vworld.kr/req/wmts/1.0.0/{key}/Satellite/{z}/{y}/{x}.jpeg"


# url_fn(z,x,y)->str, referer_env: 도메인잠금 헤더, attribution: 출처 표기
BASEMAPS = {
    "vworld": {
        "url_fn": _vworld_url,
        "referer_env": "VWORLD_REFERER",
        "attribution": "항공영상 © VWorld",
        "fmt": "jpeg",
    },
    # 카카오 스카이뷰 폴백 자리 (P2 게이트에서 VWorld 확정돼 미구현)
    "kakao": {
        "url_fn": None,
        "referer_env": None,
        "attribution": "스카이뷰 © Kakao",
        "fmt": "jpeg",
    },
}


class BasemapError(RuntimeError):
    """배경 타일 수신 실패 / 미구현 배경."""


# ── 좌표 변환 ────────────────────────────────────────────────
def ground_resolution(lat: float, z: int) -> float:
    """해당 위도·줌에서 m/픽셀."""
    return _EQUATOR_MPP_Z0 * math.cos(math.radians(lat)) / (2 ** z)


def meters_to_pixels(meters: float, lat: float, z: int) -> float:
    """거리(m) → 픽셀 (위도 보정)."""
    return meters / ground_resolution(lat, z)


def latlon_to_global_px(lat: float, lon: float, z: int) -> tuple[float, float]:
    """WGS84 → 전역 픽셀 좌표 (zoom z 전체 월드 기준)."""
    world = TILE_SIZE * (2 ** z)
    x = (lon + 180.0) / 360.0 * world
    sin_lat = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * world
    return x, y


def zoom_for_radius(lat: float, radius_m: float, target_px: float) -> int:
    """반경(m)이 target_px 픽셀 이내에 들어오는 최대 줌 (클램프 6~18)."""
    # radius_px = radius_m * 2^z / (EQ_MPP_Z0 * cos(lat)) <= target_px
    denom = radius_m
    if denom <= 0:
        return 16
    val = target_px * _EQUATOR_MPP_Z0 * math.cos(math.radians(lat)) / denom
    z = int(math.floor(math.log2(val))) if val > 0 else 16
    return max(6, min(18, z))


# ── 타일 수신 + 합성 ─────────────────────────────────────────
def _fetch_tile(
    client: httpx.Client,
    url: str,
    headers: dict,
    cache_dir: Optional[Path],
    cache_key: str,
) -> Optional[bytes]:
    """타일 1장. 디스크 캐시 우선. 실패 시 None."""
    if cache_dir is not None:
        cpath = cache_dir / cache_key
        if cpath.exists():
            return cpath.read_bytes()
    try:
        r = client.get(url, headers=headers, timeout=15.0, follow_redirects=True)
    except Exception:
        return None
    if r.status_code != 200 or r.content[:2] != b"\xff\xd8":  # jpeg 매직바이트
        return None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / cache_key).write_bytes(r.content)
    return r.content


def compose_basemap(
    lat: float,
    lon: float,
    z: int,
    width: int,
    height: int,
    basemap: str,
    client: Optional[httpx.Client] = None,
    cache_dir: Optional[Path] = None,
) -> tuple[Image.Image, tuple[float, float]]:
    """중심 좌표 기준 width×height 배경 이미지 + 중심의 전역픽셀 좌표 반환.

    누락 타일은 회색으로 채워 합성은 계속 (부분 실패에도 멈추지 않음).
    """
    spec = BASEMAPS.get(basemap)
    if spec is None or spec["url_fn"] is None:
        raise BasemapError(f"배경 '{basemap}' 미구현 (사용 가능: vworld).")

    own = client is None
    client = client or httpx.Client(timeout=15.0)
    headers = {}
    ref_env = spec.get("referer_env")
    if ref_env and os.getenv(ref_env):
        headers["Referer"] = os.getenv(ref_env)

    try:
        cx, cy = latlon_to_global_px(lat, lon, z)
        # 캔버스 좌상단의 전역픽셀
        origin_x = cx - width / 2
        origin_y = cy - height / 2

        canvas = Image.new("RGB", (width, height), (60, 60, 60))

        # 덮어야 할 타일 인덱스 범위
        tx0 = int(math.floor(origin_x / TILE_SIZE))
        ty0 = int(math.floor(origin_y / TILE_SIZE))
        tx1 = int(math.floor((origin_x + width) / TILE_SIZE))
        ty1 = int(math.floor((origin_y + height) / TILE_SIZE))
        n = 2 ** z

        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                if ty < 0 or ty >= n:
                    continue
                wrapped_tx = tx % n  # 경도 wrap
                url = spec["url_fn"](z, wrapped_tx, ty)
                data = _fetch_tile(
                    client, url, headers, cache_dir, f"{basemap}_{z}_{wrapped_tx}_{ty}.jpg"
                )
                if not data:
                    continue
                try:
                    tile_img = Image.open(io.BytesIO(data)).convert("RGB")
                except Exception:
                    continue
                px = int(round(tx * TILE_SIZE - origin_x))
                py = int(round(ty * TILE_SIZE - origin_y))
                canvas.paste(tile_img, (px, py))

        return canvas, (cx, cy)
    finally:
        if own:
            client.close()
