"""모드 A 라우터 — POST /analyze.

P5: 주소→시군구코드→KOSIS facts(실수치)→함의 룩업. 캐시 우선.
P12: _common(에어코리아 등 용도 무관) facts 병합.
데이터로 답 못하면 ErrorBlock 하드블록 (추정 금지, 절대 원칙 3).
한 문단 서술(narrative)은 P6 — Claude 1회, 실패 시 규칙 폴백.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas import AnalyzeRequest, ErrorBlock, RegionStat
from app.schemas.region import Fact, Implication, Region
from app.services.implications import derive_implications
from app.services.kakao import KakaoError, coord_to_hdong
from app.services.matrix import list_items
from app.services.narrative import compose_narrative
from app.services.resolve import resolve_address
from app.services.stats import collect_common_facts, collect_facts

router = APIRouter(tags=["mode-a"])


def _error(code: str, message: str) -> JSONResponse:
    """ErrorBlock 하드블록 응답 (422)."""
    return JSONResponse(status_code=422, content=ErrorBlock(code=code, message=message).model_dump())


def _apply_radius(facts: list, notes: list, loc, radius: int) -> bool:
    """반경 모드: SGIS 집계구 합산으로 인구/연령 facts 교체 + 인구밀도·평균나이 신규.

    KOSIS가 못 주는 반경 내 실인구 (보간 아닌 집계구 합산, 절대 원칙 1·3). 성공 시 True.
    인구 외 facts(가구·대기질 등)는 시군구 그대로 — scope 로 구분 표기 (절대 원칙 4).
    """
    from app.services import sgis

    try:
        rp = sgis.fetch_radius_population(loc.lat, loc.lon, radius)
    except Exception as e:  # noqa: BLE001 — graceful (절대 원칙 3)
        notes.append(f"SGIS 반경 인구 조회 오류: {e}")
        return False
    if not rp:
        notes.append("SGIS 반경 인구 미확보 — 시군구 기준으로 폴백.")
        return False

    scope = f"반경 {radius}m"
    yr = int(rp.get("base_year") or 0)
    share_map = {
        "고령인구비율": rp.get("aged_share"),
        "유소년인구비율": rp.get("youth_share"),
        "생산가능인구비율": rp.get("working_share"),
        "총인구수": rp.get("total_pop"),
    }
    for f in facts:
        sv = share_map.get(f["item"])
        if sv is not None:
            f["value"] = sv  # national_avg(전국) 는 KOSIS 값 유지 — 비교 일관
            f["scope"], f["scope_level"] = scope, "반경"
            f["source_tbl"], f["year"] = "SGIS 집계구", yr
    # KOSIS 시군구에 없던 신규 지표 (반경 한정)
    for item, val, unit in (
        ("인구밀도", rp.get("density_per_km2"), "명/㎢"),
        ("평균나이", rp.get("avg_age"), "세"),
    ):
        if val is not None:
            facts.append({
                "item": item, "value": val, "national_avg": None, "unit": unit,
                "source_tbl": "SGIS 집계구", "year": yr, "source_type": "sgis",
                "scope": scope, "scope_level": "반경",
            })
    notes += rp.get("notes", [])
    return True


@router.post("/analyze", response_model=None)
def analyze(req: AnalyzeRequest):
    """지역 통계 facts + 함의. 데이터 없으면 ErrorBlock."""
    # 1) 주소 → 시군구코드 (P1.6 resolve 재사용)
    try:
        loc = resolve_address(req.address)
    except KakaoError as e:
        return _error("ADDR_UNRESOLVED", f"주소 해석 불가: {e}")
    if not loc.sgg_code:
        return _error("NO_REGION_CODE", "시군구 코드를 확인할 수 없습니다.")

    # 1.5) 용도 유효성 — 알 수 없는 용도면 _common(대기질 등) 병합 전에 하드블록
    if list_items(req.use_type) is None:
        return _error("NO_DATA", f"알 수 없는 용도: {req.use_type}")

    # 1.6) 읍면동 요청이면 행정동 H코드 lazy 조회. '반경'은 KOSIS가 못하므로 시군구 baseline 후 SGIS로 덮음.
    notes_pre: list = []
    hcode = hdong = ""
    kosis_res = "시군구" if req.resolution == "반경" else req.resolution
    if kosis_res == "읍면동":
        hd = coord_to_hdong(loc.lat, loc.lon)
        if hd and hd.get("code"):
            hcode, hdong = hd["code"], hd.get("name", "")
        else:
            notes_pre.append("행정동 해석 실패 — 시군구 기준으로 폴백.")

    # 2) matrix 항목을 source_type별로 채워 facts (캐시 우선, P12)
    facts, notes, year = collect_facts(
        loc.sgg_code,
        req.use_type,
        req.year,
        sigungu=loc.sigungu,
        sido=loc.sido,
        resolution=kosis_res,
        hcode=hcode,
        hdong=hdong,
    )
    notes = notes_pre + notes

    # 3) _common 항목 병합 (에어코리아 등 용도 무관 공통)
    common_facts, common_notes = collect_common_facts(
        sido=loc.sido,
        sigungu=loc.sigungu,
    )
    facts = facts + common_facts
    notes = notes + common_notes

    # 3.5) 반경 모드 — SGIS 집계구 합산으로 인구/연령 facts 교체 + 인구밀도·평균나이 신규 (D2)
    radius_ok = False
    if req.resolution == "반경":
        radius_ok = _apply_radius(facts, notes, loc, req.radius)

    if not facts:
        return _error(
            "NO_DATA",
            f"제공된 데이터로는 확인 불가 ({req.use_type}, {loc.sigungu or loc.sgg_code}).",
        )

    # 4) 함의 룩업 (규칙 기반, LLM 없음 — 절대 원칙 2)
    imps = derive_implications(facts, use_type=req.use_type)

    # 4.5) 해상도 달성 표기 (반경 > 읍면동 > 시군구). facts scope_level 로 실제 달성 확인.
    dong_ok = hcode and any(f.get("scope_level") == "읍면동" for f in facts)
    gu_name = loc.sigungu or loc.sgg_code
    if radius_ok:
        region_name = f"{gu_name} 반경 {req.radius}m"
        region = Region(name=region_name, code=loc.sgg_code, resolution="반경")
    elif dong_ok:
        region = Region(name=hdong or "행정동", code=hcode, resolution="읍면동")
        region_name = hdong or gu_name
    else:
        region = Region(name=gu_name, code=loc.sgg_code, resolution="시군구")
        region_name = gu_name

    # 5) 한 문단 서술 (Claude 1회, 실패 시 규칙 폴백). 기준 지역·연도 명시 (절대 원칙 4)
    draft, source = compose_narrative(region_name, year or 0, req.use_type, facts, imps)

    region_stat = RegionStat(
        region=region,
        year=year or 0,
        use_type=req.use_type,
        facts=[Fact(**f) for f in facts],
        implications=[Implication(**i) for i in imps],
        draft_paragraph=draft,
        source=source,
        notes=notes,
    )
    return region_stat
