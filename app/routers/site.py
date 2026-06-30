"""대지 기본 정보 라우터 — POST /site.

위치 기반 부동산·건물 정보: 아파트 실거래가, 표준지 공시지가, 건축물대장.
각 API 독립 호출 — 하나 실패해도 나머지 반환 (부분 실패 격리).
값은 실제 API(국토부 data.go.kr)에서만. 추정 없음 (절대 원칙 1·3).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.errors import ErrorBlock
from app.schemas.site import (
    BuildingInfo,
    HazardZone,
    HeatwaveHistory,
    LandPrice,
    RealEstate,
    SiteCenter,
    SiteHazards,
    SiteInfo,
    SiteRequest,
    Transaction,
)
from app.services import molit, sgis, vworld
from app.services.cache import default_cache
from app.services.kakao import KakaoError
from app.services.resolve import resolve_address

router = APIRouter(tags=["site"])


def _error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorBlock(code=code, message=message).model_dump())


def _gather(label: str, fn):
    """1블록 수집 — 예외도 graceful 흡수 (절대 원칙 3). Returns (data, notes)."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 — 한 블록 실패가 /site 전체를 막지 않도록
        return None, [f"{label}: 수집 실패 ({type(e).__name__})."]


@router.post("/site", response_model=None)
def site_info(req: SiteRequest):
    """대지 주소 → 아파트 실거래가 · 표준지 공시지가 · 건축물대장."""

    # 1) 주소 해석
    try:
        loc = resolve_address(req.address)
    except KakaoError as e:
        return _error("ADDR_UNRESOLVED", f"주소 해석 불가: {e}")

    notes: list = list(loc.notes)
    cache = default_cache  # 토큰·위험목록·폭염 월별 캐시 공유 (반복 호출·rate-limit 회피)

    # 2~5) 독립 블록 병렬 — resolve 뒤 4블록은 서로 독립(건축물대장만 공시지가 PNU에 의존 → 한 thunk로 체인).
    # 재해위험·폭염은 SGIS 호출이 많아 순차 시 /site 가 무거웠음 → 병렬로 가장 느린 1블록 시간으로 단축.
    def _trades():
        # 4종 RTMS 가 각 ~1~2s 라 순차 시 long pole → 종류별 병렬 (종류 순서 유지해 결정적).
        kinds = molit.DEFAULT_TRADE_KINDS
        with ThreadPoolExecutor(max_workers=len(kinds)) as tex:
            futs = [tex.submit(molit.fetch_trades, k, loc.sgg_code, 3, 5) for k in kinds]
            pairs = [f.result() for f in futs]
        trades, n = [], []
        for t_raw, t_notes in pairs:
            trades.extend(t_raw)
            n.extend(t_notes)
        return {"trades": trades}, n

    def _land_building():
        n = []
        lp_raw, lp_n = vworld.fetch_land_price(loc.lon, loc.lat)
        n.extend(lp_n)
        bld_raw, bld_n = molit.fetch_building(lp_raw.get("pnu", "") if lp_raw else "")
        n.extend(bld_n)
        return {"land": lp_raw, "building": bld_raw}, n

    def _hazards():
        hz = sgis.fetch_site_hazards(loc.lat, loc.lon, dong_name=loc.eupmyeondong, cache=cache)
        return {"hz": hz}, (hz.get("notes", []) if hz else ["재해위험(SGIS) 미확보 — 위험지도 영향범위 확인 불가."])

    def _heatwave():
        hw = sgis.fetch_heatwave_history(loc.sido, loc.sigungu, cache=cache)
        return {"hw": hw}, (hw.get("notes", []) if hw else [])

    tasks = [
        ("trades", lambda: _gather("실거래", _trades)),
        ("land_building", lambda: _gather("공시지가·건축물대장", _land_building)),
        ("hazards", lambda: _gather("재해위험", _hazards)),
        ("heatwave", lambda: _gather("폭염특보", _heatwave)),
    ]
    results: dict = {}
    with ThreadPoolExecutor(max_workers=len(tasks)) as ex:
        futs = {ex.submit(thunk): key for key, thunk in tasks}
        for fut in as_completed(futs):
            results[futs[fut]] = fut.result()

    # 조립 — tasks 순서대로 notes 병합 (결정적)
    r_trades, n = results["trades"]; notes += n
    r_lb, n = results["land_building"]; notes += n
    r_hz, n = results["hazards"]; notes += n
    r_hw, n = results["heatwave"]; notes += n
    r_trades = r_trades or {}
    r_lb = r_lb or {}
    lp_raw = r_lb.get("land")
    bld_raw = r_lb.get("building")
    hz = (r_hz or {}).get("hz")
    hw = (r_hw or {}).get("hw")

    real_estate = RealEstate(
        transactions=[Transaction(**t) for t in r_trades.get("trades", [])],
        kinds=molit.DEFAULT_TRADE_KINDS,
        period="최근 3개월",
        note=f"{loc.sigungu or loc.sgg_code} 기준 (시군구 평균 아님 — 개별 거래)",
    )
    land_price = LandPrice(
        price_per_sqm=lp_raw["price_per_sqm"] if lp_raw else None,
        year=lp_raw["year"] if lp_raw else None,
        pnu=lp_raw.get("pnu", "") if lp_raw else "",
        addr=lp_raw.get("addr", "") if lp_raw else "",
        jibun=lp_raw.get("jibun", "") if lp_raw else "",
        note="좌표가 속한 필지의 개별공시지가 (VWorld — 참고)",
    )
    building = BuildingInfo(**(bld_raw or {}), note="해당 필지 건축물대장 (건축HUB — 참고)")

    if hz:
        hazards = SiteHazards(
            dong_name=hz.get("dong_name", "") or loc.eupmyeondong,
            flood=HazardZone(**hz.get("flood", {})),
            landslide=HazardZone(**hz.get("landslide", {})),
            base_year=hz.get("base_year", ""),
        )
    else:
        hazards = SiteHazards(dong_name=loc.eupmyeondong)
    if hw:
        hazards.heatwave = HeatwaveHistory(
            alert_count=hw.get("alert_count", 0),
            warning_count=hw.get("warning_count", 0),
            scope=hw.get("scope", ""),
            base_period=hw.get("base_period", ""),
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
        hazards=hazards,
        base_date=date.today().isoformat(),
        notes=notes,
    )
