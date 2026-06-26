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
    AptTrade,
    BuildingInfo,
    LandPrice,
    RealEstate,
    SiteCenter,
    SiteInfo,
    SiteRequest,
)
from app.services import molit
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

    # 2) 아파트 실거래가 (시군구코드 → 최근 3개월)
    trades_raw, trade_notes = molit.fetch_apt_trade(loc.sgg_code, months=3, max_items=10)
    notes.extend(trade_notes)
    real_estate = RealEstate(
        transactions=[AptTrade(**t) for t in trades_raw],
        period="최근 3개월",
        note=f"{loc.sigungu or loc.sgg_code} 기준 (시군구 평균 아님 — 개별 거래)",
    )

    # 3) 표준지 공시지가 (좌표 기반)
    lp_raw, lp_notes = molit.fetch_land_price(loc.lon, loc.lat)
    notes.extend(lp_notes)
    land_price = LandPrice(
        price_per_sqm=lp_raw["price_per_sqm"] if lp_raw else None,
        year=lp_raw["year"] if lp_raw else None,
        pnu=lp_raw.get("pnu", "") if lp_raw else "",
        note="좌표 기준 인근 표준지 가격 (해당 필지 개별 공시지가 아님 — 참고)",
    )

    # 4) 건축물대장 (시도+시군구+법정동 기준)
    bld_raw, bld_notes = molit.fetch_building(loc.sido, loc.sigungu, loc.eupmyeondong)
    notes.extend(bld_notes)
    building = BuildingInfo(
        **(bld_raw or {}),
        note=f"{loc.sigungu} {loc.eupmyeondong} 첫 건물 기준 (해당 대지 건물과 다를 수 있음 — 참고)",
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
