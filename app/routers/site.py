"""대지 기본 정보 라우터 — POST /site.

위치 기반 부동산·건물 정보: 아파트 실거래가, 표준지 공시지가, 건축물대장.
각 API 독립 호출 — 하나 실패해도 나머지 반환 (부분 실패 격리).
값은 실제 API(국토부 data.go.kr)에서만. 추정 없음 (절대 원칙 1·3).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.errors import ErrorBlock
from app.schemas.site import (
    BuildingInfo,
    LandPrice,
    RealEstate,
    SiteCenter,
    SiteInfo,
    SiteRequest,
    Transaction,
)
from app.services import molit, vworld
from app.services.kakao import KakaoError
from app.services.resolve import resolve_address

router = APIRouter(tags=["site"])


def _error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorBlock(code=code, message=message).model_dump())


@router.post("/site", response_model=None)
def site_info(req: SiteRequest):
    """대지 주소 → 아파트 실거래가 · 표준지 공시지가 · 건축물대장."""

    # 1) 주소 해석
    try:
        loc = resolve_address(req.address)
    except KakaoError as e:
        return _error("ADDR_UNRESOLVED", f"주소 해석 불가: {e}")

    notes: list = list(loc.notes)

    # 2) 실거래가 (시군구코드 → 최근 3개월, 종류별 — 토지매매 우선)
    all_trades: list = []
    for kind in molit.DEFAULT_TRADE_KINDS:
        t_raw, t_notes = molit.fetch_trades(kind, loc.sgg_code, months=3, max_items=5)
        all_trades.extend(t_raw)
        notes.extend(t_notes)
    real_estate = RealEstate(
        transactions=[Transaction(**t) for t in all_trades],
        kinds=molit.DEFAULT_TRADE_KINDS,
        period="최근 3개월",
        note=f"{loc.sigungu or loc.sgg_code} 기준 (시군구 평균 아님 — 개별 거래)",
    )

    # 3) 개별공시지가 (좌표가 속한 필지 — VWorld 연속지적도, data.go.kr 미승인 우회)
    lp_raw, lp_notes = vworld.fetch_land_price(loc.lon, loc.lat)
    notes.extend(lp_notes)
    land_price = LandPrice(
        price_per_sqm=lp_raw["price_per_sqm"] if lp_raw else None,
        year=lp_raw["year"] if lp_raw else None,
        pnu=lp_raw.get("pnu", "") if lp_raw else "",
        addr=lp_raw.get("addr", "") if lp_raw else "",
        jibun=lp_raw.get("jibun", "") if lp_raw else "",
        note="좌표가 속한 필지의 개별공시지가 (VWorld — 참고)",
    )

    # 4) 건축물대장 (건축HUB, 공시지가에서 얻은 PNU 필지 기준)
    pnu = lp_raw.get("pnu", "") if lp_raw else ""
    bld_raw, bld_notes = molit.fetch_building(pnu)
    notes.extend(bld_notes)
    building = BuildingInfo(
        **(bld_raw or {}),
        note="해당 필지 건축물대장 (건축HUB — 참고)",
    )

    return SiteInfo(
        center=SiteCenter(
            lat=loc.lat,
            lon=loc.lon,
            address=loc.address,
            sido=loc.sido,
            sigungu=loc.sigungu,
            dong=loc.eupmyeondong,
        ),
        real_estate=real_estate,
        land_price=land_price,
        building=building,
        base_date=date.today().isoformat(),
        notes=notes,
    )
