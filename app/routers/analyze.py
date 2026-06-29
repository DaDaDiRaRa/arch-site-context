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
from app.services.kakao import KakaoError
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

    # 2) matrix 항목을 source_type별로 채워 facts (캐시 우선, P12)
    facts, notes, year = collect_facts(
        loc.sgg_code,
        req.use_type,
        req.year,
        sigungu=loc.sigungu,
        sido=loc.sido,
    )

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

    # 5) 한 문단 서술 (Claude 1회, 실패 시 규칙 폴백). '○○구 기준'·연도 명시 (절대 원칙 4)
    region_name = loc.sigungu or loc.sgg_code
    draft, source = compose_narrative(region_name, year or 0, req.use_type, facts, imps)

    region_stat = RegionStat(
        region=Region(name=region_name, code=loc.sgg_code, resolution="시군구"),
        year=year or 0,
        use_type=req.use_type,
        facts=[Fact(**f) for f in facts],
        implications=[Implication(**i) for i in imps],
        draft_paragraph=draft,
        source=source,
        notes=notes,
    )
    return region_stat
