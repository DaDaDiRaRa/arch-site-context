"""모드 B 라우터 — POST /facilities, POST /facilities/map.

/facilities: 카카오 로컬 실제 호출 (P1 구현 완료).
/facilities/map: VWorld 위성 배경 + 핀·반경원·범례·출처 합성 PNG (P3).
"""

from __future__ import annotations

import hashlib
import io

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import OUT_DIR
from app.schemas import FacilityRequest, FacilityResult, MapRequest
from app.schemas.facility import DEFAULT_KINDS, DEFAULT_RADII
from app.services.facilities import build_facility_result
from app.services.kakao import KakaoError
from app.services.map_compose import compose_map
from app.services.tiles import BasemapError
from app.services import tiles, tmap

router = APIRouter(tags=["mode-b"])

# 저장 위치: OUT_DIR/maps (StaticFiles 로 /files 에 마운트). 타일 캐시: OUT_DIR/tile_cache
_MAPS_DIR = OUT_DIR / "maps"
_TILE_CACHE = OUT_DIR / "tile_cache"


class BasemapRequest(BaseModel):
    """POST /basemap 입력 — 좌표는 상위(카카오)에서 해석해 넘긴다."""

    lat: float
    lon: float
    radius: int = 1000
    size_px: int = 1200


@router.post("/basemap")
def basemap(req: BasemapRequest) -> dict:
    """주석 없는 깨끗한 위성 배경 + 지오참조(줌·중심 전역픽셀·반경픽셀).

    소비자(deck-builder 등)가 그 위에 **네이티브 편집가능 도형**(반경원·핀)을 직접 그리도록
    좌표계 메타를 함께 반환. (합성 PNG /facilities/map 과 달리 주석을 굽지 않음.)
    """
    size = max(400, min(2000, req.size_px))
    try:
        z = tiles.zoom_for_radius(req.lat, req.radius, size / 2 - 60)
        img, (cx, cy) = tiles.compose_basemap(
            req.lat, req.lon, z, size, size, "vworld", cache_dir=_TILE_CACHE
        )
    except BasemapError as e:
        raise HTTPException(status_code=422, detail=str(e))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    sig = f"base|{req.lat:.6f}|{req.lon:.6f}|{req.radius}|{size}"
    name = "base_" + hashlib.sha1(sig.encode("utf-8")).hexdigest()[:16] + ".png"
    _MAPS_DIR.mkdir(parents=True, exist_ok=True)
    (_MAPS_DIR / name).write_bytes(buf.getvalue())
    return {
        "url": f"/files/maps/{name}",
        "zoom": z, "cx": cx, "cy": cy, "size_px": size,
        "radius_px": tiles.meters_to_pixels(req.radius, req.lat, z),
        "lat": req.lat, "lon": req.lon,
    }


@router.post("/facilities", response_model=FacilityResult)
def facilities(req: FacilityRequest) -> FacilityResult:
    """반경 내 시설 목록·개수 (카카오 로컬). 0건도 정상(빈 배열+0)."""
    kinds = req.kinds or list(DEFAULT_KINDS)
    radii = req.radii or list(DEFAULT_RADII)
    try:
        return build_facility_result(req.address, kinds, radii)
    except KakaoError as e:
        # 주소 해석 불가·키 문제 등은 추정 대신 명확히 멈춘다 (절대 원칙 3).
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/facilities/map")
def facilities_map(req: MapRequest) -> dict:
    """P1 결과 위에 위성 배경·핀·반경원·범례·출처를 합성한 PNG 저장 후 경로/URL 반환."""
    kinds = req.kinds or list(DEFAULT_KINDS)
    radii = req.radii or list(DEFAULT_RADII)
    try:
        result = build_facility_result(req.address, kinds, radii)

        iso = None
        if req.isochrone and tmap._TMAP_KEY:
            try:
                iso = tmap.compute_isochrone(result.center.lat, result.center.lon)
            except Exception:
                result.notes.append("TMAP 등시선 계산 실패 — 직선반경으로 표시.")

        png = compose_map(result, radii, basemap=req.basemap, isochrone=iso, cache_dir=_TILE_CACHE)
    except KakaoError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except BasemapError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 요청 내용 기반 안정적 파일명 (동일 요청 재사용)
    sig = f"{req.address}|{','.join(kinds)}|{','.join(map(str, radii))}|{req.basemap}"
    name = "map_" + hashlib.sha1(sig.encode("utf-8")).hexdigest()[:16] + ".png"
    _MAPS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _MAPS_DIR / name
    out_path.write_bytes(png)

    return {
        "png_path": str(out_path),
        "url": f"/files/maps/{name}",
        "bytes": len(png),
        "center": result.center.model_dump(),
        "counts": result.counts,
        "basemap": req.basemap,
        "source": result.source,
        "base_date": result.base_date,
        "notes": result.notes,
    }
