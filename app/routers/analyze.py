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

    # 1.6) 읍면동 요청이면 행정동 H코드 lazy 조회 (좌표→coord2regioncode). 실패 시 구로 폴백.
    notes_pre: list = []
    hcode = hdong = ""
    if req.resolution == "읍면동":
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
        resolution=req.resolution,
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

    if not facts:
        return _error(
            "NO_DATA",
            f"제공된 데이터로는 확인 불가 ({req.use_type}, {loc.sigungu or loc.sgg_code}).",
        )

    # 4) 함의 룩업 (규칙 기반, LLM 없음 — 절대 원칙 2)
    imps = derive_implications(facts, use_type=req.use_type)

    # 4.5) 동 해상도 달성 여부 — facts 중 읍면동 scope 가 하나라도 있으면 동 모드로 표기
    dong_ok = hcode and any(f.get("scope_level") == "읍면동" for f in facts)
    gu_name = loc.sigungu or loc.sgg_code
    if dong_ok:
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
