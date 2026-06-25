"""모드 B 라우터 — POST /facilities, POST /facilities/map.

/facilities: 카카오 로컬 실제 호출 (P1 구현 완료).
/facilities/map: VWorld 위성 배경 + 핀·반경원·범례·출처 합성 PNG (P3).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas import FacilityRequest, FacilityResult, MapRequest
from app.schemas.facility import DEFAULT_KINDS, DEFAULT_RADII
from app.services.facilities import build_facility_result
from app.services.kakao import KakaoError
from app.services.map_compose import compose_map
from app.services.tiles import BasemapError

router = APIRouter(tags=["mode-b"])

# 저장 위치: out/maps (StaticFiles 로 /files 에 마운트 — main.py). 타일 캐시: out/tile_cache
_OUT = Path(__file__).resolve().parent.parent.parent / "out"
_MAPS_DIR = _OUT / "maps"
_TILE_CACHE = _OUT / "tile_cache"


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
        png = compose_map(result, radii, basemap=req.basemap, cache_dir=_TILE_CACHE)
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


@router.post("/facilities/map")
def facilities_map(req: MapRequest) -> StreamingResponse:
    """위성 PNG (핀·반경). (P0 스텁 — 1x1 투명 PNG 플레이스홀더 반환)"""
    # 최소 유효 PNG 1x1 (실제 VWorld 타일 합성은 P3)
    png_1x1 = bytes(
        [
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
            0x89, 0x00, 0x00, 0x00, 0x0D, 0x49, 0x44, 0x41,
            0x54, 0x78, 0x9C, 0x62, 0x00, 0x01, 0x00, 0x00,
            0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
            0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,
            0x42, 0x60, 0x82,
        ]
    )
    return StreamingResponse(
        iter([png_1x1]),
        media_type="image/png",
        headers={"X-Stub": "P0-placeholder"},
    )
