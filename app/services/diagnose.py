"""P11 수급진단 오케스트레이션 — A(인구 수요) × B(시설 공급) 교차.

흐름: 주소 → resolve(시군구) → demand(collect_facts_by_items) + supply(build_facility_result)
      → 규칙별 수요·공급 레벨 교차 → 진단[]. 시장에 없는 조합 (CLAUDE.md §8 P11).

부족/과잉은 휴리스틱이므로 signal·소견은 모두 '참고', 원수치 항상 노출, 판단은 사람
(절대 원칙 5). 수치(레벨·개수)는 코드/규칙이 만든다 (절대 원칙 2). 임계값은 JSON (원칙 7).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import List, Optional

import httpx

from app.schemas.diagnose import (
    Diagnosis,
    DemandSignal,
    DiagnoseResult,
    SupplySignal,
)
from app.schemas.facility import Center
from app.schemas.region import Region
from app.services import stats
from app.services.cache import Cache
from app.services.facilities import build_facility_result
from app.services.resolve import resolve_address

_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "supply_demand.json"


def load_rules() -> List[dict]:
    """supply_demand.json 규칙 배열. 없으면 빈 리스트 (설정은 JSON — 절대 원칙 7)."""
    if not _RULES_PATH.exists():
        return []
    return json.loads(_RULES_PATH.read_text(encoding="utf-8")).get("rules", [])


def _demand_level(value: float, national: Optional[float], margin: float) -> str:
    """전국 대비 수요 레벨. 비교기준 없으면 '불명' (추정 안 함, 절대 원칙 3)."""
    if national is None:
        return "불명"
    if value > national + margin:
        return "높음"
    if value < national - margin:
        return "낮음"
    return "평이"


def _supply_level(count: int, low_max: int, high_min: int) -> str:
    """반경 내 공급 개수 레벨."""
    if count <= low_max:
        return "적음"
    if count >= high_min:
        return "많음"
    return "보통"


# 수요×공급 조합 → 한 줄 소견(참고). 단정 금지, '점검'으로 재료만 제시 (절대 원칙 5).
_VERDICT = {
    ("높음", "적음"): "수요 높음 대비 공급 적음 — 공급 부족 가능성 점검",
    ("높음", "보통"): "수요 높음, 공급 보통 — 적정성 점검",
    ("높음", "많음"): "수요·공급 모두 높음 — 적정성 점검",
    ("평이", "적음"): "수요 평이, 공급 적음 — 추이 점검",
    ("평이", "보통"): "수요·공급 균형권 — 특이신호 약함",
    ("평이", "많음"): "수요 평이 대비 공급 많음 — 과잉 여부 점검",
    ("낮음", "적음"): "수요·공급 모두 낮음 — 특이신호 약함",
    ("낮음", "보통"): "수요 낮음 대비 공급 보통 — 과잉 여부 점검",
    ("낮음", "많음"): "수요 낮음 대비 공급 많음 — 과잉 여부 점검",
}


def _verdict(dlevel: str, slevel: str) -> str:
    if dlevel == "불명":
        return "전국 비교 불가(수요 불명) — 공급 개수만 참고"
    return _VERDICT.get((dlevel, slevel), "특이신호 약함")


def cross_rules(
    fact_by_item: dict, band: dict, radius: int, rules: Optional[List[dict]] = None
) -> tuple:
    """수요 facts × 공급 개수(band)를 규칙과 교차 → (diagnoses, notes).

    순수 로직(네트워크 없음) — build_diagnosis 와 P9 비교(compare)가 공유.
    band: {시설종류: 반경내 개수}. fact_by_item: {지표명: fact dict}.
    """
    rules = rules if rules is not None else load_rules()
    diagnoses: List[Diagnosis] = []
    notes: List[str] = []
    for r in rules:
        fact = fact_by_item.get(r["demand_item"])
        if fact is None:
            notes.append(
                f"'{r['name']}': 수요지표 '{r['demand_item']}' 데이터 없음 — 진단 건너뜀."
            )
            continue
        dlevel = _demand_level(
            float(fact["value"]),
            fact.get("national_avg"),
            float(r.get("demand_margin", 0)),
        )
        count = sum(int(band.get(k, 0)) for k in r["supply_kinds"])
        slevel = _supply_level(
            count, int(r.get("supply_low_max", 0)), int(r.get("supply_high_min", 10**9))
        )
        verdict = _verdict(dlevel, slevel)
        unit = fact.get("unit", "")
        nat = fact.get("national_avg")
        nat_txt = f"전국 {nat}{unit}" if nat is not None else "전국 비교 불가"
        note = (
            f"{r['demand_item']} {fact['value']}{unit}({nat_txt}) · "
            f"반경 {radius}m {'·'.join(r['supply_kinds'])} {count}개 — {verdict}"
        )
        diagnoses.append(
            Diagnosis(
                name=r["name"],
                demand=DemandSignal(
                    item=fact["item"],
                    value=fact["value"],
                    national_avg=nat,
                    unit=unit,
                    level=dlevel,
                    source_tbl=fact["source_tbl"],
                    year=fact["year"],
                ),
                supply=SupplySignal(
                    kinds=r["supply_kinds"], count=count, radius=radius, level=slevel
                ),
                signal=f"수요 {dlevel}·공급 {slevel}",
                note=note,
                tag=r.get("tag", "참고"),
            )
        )
    return diagnoses, notes


def build_diagnosis(
    address: str,
    radius: int = 1000,
    client: Optional[httpx.Client] = None,
    cache: Optional[Cache] = None,
) -> DiagnoseResult:
    """수급진단 결과 구성. demand facts 가 하나도 없으면 diagnoses 빈 배열(라우터가 ErrorBlock)."""
    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        loc = resolve_address(address, client=client)
        rules = load_rules()
        notes: List[str] = list(loc.notes)

        # demand: 규칙들의 distinct demand_item 모아 1세트 호출 (시군구 평균 — 절대 원칙 4)
        demand_items = list(dict.fromkeys(r["demand_item"] for r in rules))
        facts, dnotes, year = stats.collect_facts_by_items(
            loc.sgg_code, demand_items, sigungu=loc.sigungu, cache=cache
        )
        notes += dnotes
        fact_by_item = {f["item"]: f for f in facts}

        # supply: 규칙들의 모든 시설종류를 한 번에 반경검색 (모드 B 재사용)
        kinds = list(dict.fromkeys(k for r in rules for k in r["supply_kinds"]))
        fres = build_facility_result(address, kinds, [radius], client=client, loc=loc)
        band = fres.counts.get(str(radius), {})
        notes += [n for n in fres.notes if n not in notes]

        diagnoses, cnotes = cross_rules(fact_by_item, band, radius, rules)
        notes += cnotes

        return DiagnoseResult(
            center=Center(lat=loc.lat, lon=loc.lon, address=loc.address),
            region=Region(
                name=loc.sigungu or loc.sgg_code, code=loc.sgg_code, resolution="시군구"
            ),
            radius=radius,
            diagnoses=diagnoses,
            source="kakao+kosis",
            base_date=date.today().isoformat(),
            notes=notes,
        )
    finally:
        if own:
            client.close()
