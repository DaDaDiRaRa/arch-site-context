"""공동주택 대지 readout 오케스트레이션 — POST /readout.

주소 → 시군구 → ① 기존 matrix 지표(collect_facts) + ② 크랙 census 지표(census_multidim)
+ ③ 파생(밀도·비율) + 유형 프리셋 강조. 각 블록 best-effort graceful (절대 원칙 3).
시군구 평균이므로 notes 에 '○○구 기준' 캐비엇 (절대 원칙 4). scripts/demo_site_kosis.py 정식화.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

import httpx

from app.schemas.readout import (
    ContextIndicator,
    DemographicFact,
    DerivedIndicator,
    ReadoutResult,
    ReadoutSite,
)
from app.services import census_multidim, stats
from app.services.cache import Cache, default_cache
from app.services.resolve import resolve_address

# 크랙한 census 지표 정의 (org, tbl, itm, 주기, 단위, 라벨, 축, breakdown).
_CONTEXT_INDICATORS = [
    {"key": "biz", "org": "101", "tbl": "DT_1BD1032", "itm": "T01", "prd": "년",
     "unit": "개", "label": "사업체수", "axis": "산업·고용", "breakdown": True},
    {"key": "empty", "org": "101", "tbl": "DT_1JU1512", "itm": "ALL", "prd": "년",
     "unit": "호", "label": "빈집", "axis": "주거"},
    {"key": "newly", "org": "101", "tbl": "DT_1NW1037", "itm": "ALL", "prd": "년",
     "unit": "쌍", "label": "신혼부부", "axis": "주거수요"},
    {"key": "disabled", "org": "117", "tbl": "DT_11761_N009", "itm": "ALL", "prd": "년",
     "unit": "명", "label": "등록장애인", "axis": "복지"},
]

# 유형별 강조 지표(라벨·item 이름). 데이터는 동일, 표시 강조만.
_PRESET = {
    "재건축": {"고령인구비율", "빈집", "세대수", "순이동"},
    "재개발": {"빈집", "순이동", "1인가구비율", "고령인구비율"},
    "민간": {"신혼부부", "순이동", "사업체수", "유소년인구비율"},
    "주상복합": {"사업체수", "1인가구비율", "총인구수"},
}


def build_readout(
    address: str,
    use_type: str = "주거",
    project_type: str = "재건축",
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> ReadoutResult:
    """공동주택 대지 readout 구성. 각 지표 graceful — 일부 실패해도 나머지 반환."""
    cache = cache if cache is not None else default_cache
    emphasis = _PRESET.get(project_type, set())
    loc = resolve_address(address, client=client)
    notes: List[str] = list(loc.notes)
    notes.append(f"모든 수치는 {loc.sigungu or loc.sgg_code} 시군구 평균 — 대지 고유값 아님 (출처: KOSIS).")

    # ① 기존 matrix 지표 (인구·가구)
    facts, fnotes, year = stats.collect_facts(loc.sgg_code, use_type, cache=cache)
    notes += fnotes
    fact_map = {f["item"]: f for f in facts}
    demographics = [
        DemographicFact(
            item=f["item"], value=f["value"], national_avg=f.get("national_avg"),
            unit=f.get("unit", ""), source_tbl=f.get("source_tbl", ""), year=f.get("year"),
            emphasized=f["item"] in emphasis,
        )
        for f in facts
    ]

    # ② 크랙한 census 지표 (산업·주거·복지)
    context: List[ContextIndicator] = []
    census_vals: dict = {}
    own = client is None
    client = client or httpx.Client(timeout=25.0)
    try:
        for ind in _CONTEXT_INDICATORS:
            data, cnotes = census_multidim.fetch_census_indicator(
                ind["org"], ind["tbl"], ind["itm"], loc.sigungu, ind["prd"],
                sido=loc.sido,  # 동명 시군구 disambiguation (HIGH 수정)
                breakdown=ind.get("breakdown", False), cache=cache, client=client,
            )
            notes += cnotes
            val = data.get("value") if data else None
            census_vals[ind["key"]] = val
            context.append(ContextIndicator(
                label=ind["label"], value=val, unit=ind["unit"], axis=ind["axis"],
                breakdown=(data.get("breakdown", []) if data else []),
                source_tbl=ind["tbl"], year=(data.get("year") if data else None),
                emphasized=ind["label"] in emphasis,
            ))
    finally:
        if own:
            client.close()

    # ③ 파생지표 (분모: 총인구·세대수)
    pop = fact_map.get("총인구수", {}).get("value")
    sed = fact_map.get("세대수", {}).get("value")
    derived: List[DerivedIndicator] = []
    if pop and census_vals.get("biz"):
        derived.append(DerivedIndicator(label="사업체밀도", value=round(census_vals["biz"] / pop * 1000), unit="개/천명"))
    if pop and census_vals.get("disabled"):
        derived.append(DerivedIndicator(label="장애인비율", value=round(census_vals["disabled"] / pop * 100, 1), unit="%"))
    if sed and census_vals.get("newly"):
        derived.append(DerivedIndicator(label="신혼부부/세대", value=round(census_vals["newly"] / sed * 100, 1), unit="%"))

    if project_type == "민간":
        notes.append("택지·신도시 신축이면 시군구 평균이 '형성 전 신규단지'를 못 반영 — 배후 규모 참고용.")

    return ReadoutResult(
        site=ReadoutSite(
            lat=loc.lat, lon=loc.lon, address=loc.address,
            sigungu=loc.sigungu, sgg_code=loc.sgg_code,
        ),
        project_type=project_type,
        demographics=demographics,
        context=context,
        derived=derived,
        base_date=date.today().isoformat(),
        notes=notes,
    )
