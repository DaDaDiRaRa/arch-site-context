"""덱 데이터 접근 — 터읽기 내부는 직접 호출, 형제앱(model·law)만 HTTP.

deck-builder(구 별도 서비스)를 터읽기에 흡수하면서, board/facilities/surroundings/basemap 은
자기 서비스 함수를 **직접 호출**(자기 HTTP 회피)하고 model·law 만 env URL 로 호출한다.
반환은 dict(model_dump) — 슬라이드 코드가 dict.get() 으로 접근하므로. 전부 graceful(실패=None).
"""
from __future__ import annotations

import io
import math
import os
from typing import Optional

import httpx

# 형제앱 URL (env). 미설정이면 로컬 기본 — model·law 없으면 지도 매싱·용도 슬라이드는 graceful skip.
SITEMODEL_URL = os.environ.get("SITEMODEL_URL", "http://127.0.0.1:8001").rstrip("/")
LAW_URL = os.environ.get("LAW_URL", "http://127.0.0.1:8002").rstrip("/")
SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY", "")
TIMEOUT_MODEL = float(os.environ.get("TIMEOUT_MODEL", "120"))
TIMEOUT_LAW = float(os.environ.get("TIMEOUT_LAW", "60"))

# 건물명 접미사 — 매싱 라벨 매칭용 (assembler 에서 이관)
_BLDG_SUFFIX = ("아파트", "오피스텔", "맨션", "맨숀", "빌딩", "타워", "스퀘어", "병원", "학교")
_DIRS8 = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]


def _auth() -> dict:
    return {"X-API-Key": SERVICE_API_KEY} if SERVICE_API_KEY else {}


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _bearing8(lat1, lon1, lat2, lon2) -> str:
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(math.radians(lat2))
    x = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
         - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dl))
    deg = (math.degrees(math.atan2(y, x)) + 360) % 360
    return _DIRS8[int((deg + 22.5) % 360 // 45)]


# ── 터읽기 내부 직접 호출 (자기 HTTP 회피) ──

def fetch_board(address: str, use_type: str, radius: int, synthesize: bool) -> Optional[dict]:
    """종합 읽기 — /board 라우터 함수 직접 호출. 인문사회·대지·생활맥락 전부."""
    from fastapi.responses import JSONResponse

    from app.routers.board import board
    from app.schemas.board import BoardRequest
    try:
        r = board(BoardRequest(address=address, use_type=use_type, radius=radius, synthesize=synthesize))
        if isinstance(r, JSONResponse):
            return None
        return r.model_dump()
    except Exception:  # noqa: BLE001 — 덱은 board 없이도(부분) 나아가야 함
        return None


def fetch_facilities(address: str, kinds: list, radius: int) -> Optional[dict]:
    """반경 내 시설 — 서비스 직접 호출."""
    from app.services.facilities import build_facility_result
    try:
        return build_facility_result(address, kinds, [radius]).model_dump()
    except Exception:  # noqa: BLE001
        return None


def fetch_surroundings(address: str, radius: int) -> Optional[dict]:
    """주변현황도 — 서비스 직접 호출."""
    from app.services.surroundings import collect_surroundings
    try:
        return collect_surroundings(address, radius).model_dump()
    except Exception:  # noqa: BLE001
        return None


def fetch_site(address: str) -> Optional[dict]:
    """대지 기본정보 — /site 라우터 함수 직접 호출 (커버·광역 슬라이드용)."""
    from fastapi.responses import JSONResponse

    from app.routers.site import site_info
    from app.schemas.site import SiteRequest
    try:
        r = site_info(SiteRequest(address=address))
        if isinstance(r, JSONResponse):
            return None
        return r.model_dump()
    except Exception:  # noqa: BLE001
        return None


def fetch_basemap(lat: float, lon: float, radius: int, size_px: int = 1500):
    """(meta, png_bytes) — /basemap 을 in-process 재현. 네이티브 도형용 지오참조 포함."""
    try:
        from app.config import OUT_DIR
        from app.services import tiles
        size = max(400, min(2000, int(size_px)))
        z = tiles.zoom_for_radius(lat, radius, size / 2 - 60)
        img, (cx, cy) = tiles.compose_basemap(
            lat, lon, z, size, size, "vworld", cache_dir=OUT_DIR / "tile_cache"
        )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        meta = {
            "zoom": z, "cx": cx, "cy": cy, "size_px": size,
            "radius_px": tiles.meters_to_pixels(radius, lat, z), "lat": lat, "lon": lon,
        }
        return meta, buf.getvalue()
    except Exception:  # noqa: BLE001 — 지도 실패해도 표만으로 슬라이드 완결
        return None


# ── 형제앱 HTTP (model·law — env URL 필요, 없으면 graceful) ──

def fetch_model(address: str, radius_m: int) -> Optional[dict]:
    """주변 3D 매싱 — arch-site-model. env SITEMODEL_URL 미설정·미기동이면 None(지도 매싱 생략)."""
    try:
        r = httpx.post(
            f"{SITEMODEL_URL}/api/generate",
            json={"address": address, "radius_m": radius_m,
                  "layers": {"buildings": True, "terrain": True, "orthophoto": False},
                  "outputs": ["3dm"]},
            timeout=TIMEOUT_MODEL, headers=_auth(),
        )
        r.raise_for_status()
        return r.json()
    except Exception:  # noqa: BLE001
        return None


def fetch_law(address: str, pnu: str = "", lat: float | None = None, lon: float | None = None) -> Optional[dict]:
    """토지이용계획 — arch-law-diagnose. **pnu 우선**(권위·지오코딩 불필요), 없으면 address.

    ⚠ 배포된 law 는 lat/lon 만으로는 400("pnu 또는 address 필수"), lat/lon 동봉 시 '좌표 변환 실패'
    를 내므로 **lat/lon 은 보내지 않는다**. pnu(build_site 가 VWorld 로 해석)가 가장 견고.
    """
    params: dict = {}
    if pnu:
        params["pnu"] = pnu
    elif address:
        params["address"] = address
    if not params:
        return None
    try:
        r = httpx.get(f"{LAW_URL}/api/land_info", params=params, timeout=TIMEOUT_LAW, headers=_auth())
        r.raise_for_status()
        return r.json()
    except Exception:  # noqa: BLE001
        return None
