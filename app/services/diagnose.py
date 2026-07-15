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
from app.services import childcare, stats
from app.services.cache import Cache
from app.services.stats import fetch_total_pop
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


def _supply_level_count(count: int, low_max: int, high_min: int, radius: int = 1000) -> str:
    """반경 내 공급 개수 레벨. 임계값은 radius=1000m 기준 — 면적 비례(radius²)로 스케일.

    작은 반경(예: 500m→scale 0.25)에서 임계값이 뭉개지면 '보통' 밴드가 사라져
    저임계 규칙(초등학교 low0/high3)이 1개만 있어도 '많음'으로 튄다.
    → scaled_high 를 scaled_low+2 이상으로 보장해 '보통'(=scaled_low+1) 밴드를 항상 남긴다.
    (radius=1000·2000 등 정상 스케일에선 high 임계가 커서 이 하한이 발동 안 함 — 무영향.)
    """
    scale = (radius / 1000) ** 2
    scaled_low = max(0, round(low_max * scale))
    scaled_high = max(scaled_low + 2, round(high_min * scale))
    if count <= scaled_low:
        return "적음"
    if count >= scaled_high:
        return "많음"
    return "보통"


def _supply_level_density(density: float, national: float, low_pct: float, high_pct: float) -> str:
    """인구 밀도 기반 공급 레벨. 전국 대비 %로 판정."""
    if density < national * low_pct / 100:
        return "적음"
    if density >= national * high_pct / 100:
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
    fact_by_item: dict,
    band: dict,
    radius: int,
    rules: Optional[List[dict]] = None,
    capacity_data: Optional[dict] = None,
    total_pop: Optional[int] = None,
    radius_pop: Optional[int] = None,
) -> tuple:
    """수요 facts × 공급 개수(band)를 규칙과 교차 → (diagnoses, notes).

    순수 로직(네트워크 없음) — build_diagnosis 와 P9 비교(compare)가 공유.
    band: {시설종류: 반경내 개수}. fact_by_item: {지표명: fact dict}.
    capacity_data: {규칙명: {capacity, scope}} — 시군구 정원 보강(선택, 반경과 단위 다름·참고).
    total_pop: 시군구 총인구 — 밀도 계산용(선택, 참고).
    radius_pop: 반경 내 실인구(SGIS 집계구 합산) — 있으면 공급 판정을 '반경 1인당 밀도 vs 전국'으로
      격상(primary). 분자(반경 시설수)·분모(반경 실인구) 모두 실측·반경 단위 (절대 원칙 1). 없으면
      개수 임계값 fallback. 반경 모드 전용 — 구/동 모드는 None 으로 기존 동작 유지(하위호환).
    """
    rules = rules if rules is not None else load_rules()
    capacity_data = capacity_data or {}
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
        nat_density = r.get("national_density_per_10k")
        low_pct = r.get("density_low_pct")
        high_pct = r.get("density_high_pct")

        # ── 공급 밀도 (만명당 시설수) ───────────────────────────────────────
        # 분모: 반경 실인구(SGIS 집계구 합산) 우선 → 분자·분모 모두 실측·반경 단위(절대 원칙 1).
        # 없으면 시군구 총인구(공간 단위 달라 참고용).
        density_pop = radius_pop if (radius_pop and radius_pop > 0) else total_pop
        density_per_10k: Optional[float] = None
        vs_national_pct: Optional[int] = None
        if density_pop and density_pop > 0 and nat_density:
            density_per_10k = round(count / (density_pop / 10_000), 2)
            vs_national_pct = round(density_per_10k / nat_density * 100)

        # ── 공급 레벨 판정 ──────────────────────────────────────────────────
        # 반경 실인구가 있으면 '반경 1인당 밀도 vs 전국 1인당'이 primary (사과 대 사과·재현가능).
        # 그 외(구/동 모드)는 반경 비례 개수 임계값 — radius=1000m 기준 면적²로 스케일.
        if (radius_pop and radius_pop > 0 and density_per_10k is not None
                and nat_density and low_pct is not None and high_pct is not None):
            slevel = _supply_level_density(
                density_per_10k, float(nat_density), float(low_pct), float(high_pct))
            density_basis = "반경"
        else:
            slevel = _supply_level_count(
                count,
                int(r.get("supply_low_max", 0)),
                int(r.get("supply_high_min", 10**9)),
                radius,
            )
            density_basis = "시군구" if density_per_10k is not None else ""

        verdict = _verdict(dlevel, slevel)
        unit = fact.get("unit", "")
        nat = fact.get("national_avg")
        nat_txt = f"전국 {nat}{unit}" if nat is not None else "전국 비교 불가"

        # 시군구 정원 보강 (어린이집 등 — 반경 개수와 단위 다름, 참고)
        cap_info = capacity_data.get(r["name"]) or {}
        capacity = cap_info.get("capacity")
        cap_scope = cap_info.get("scope", "")
        cap_txt = (
            f"(시군구 {cap_scope} 정원 {capacity}명)" if capacity is not None else ""
        )

        # 밀도 텍스트 (분모 기준 명시 — 반경 실인구 vs 시군구 참고)
        if density_per_10k is not None and nat_density:
            basis_lbl = "반경인구" if density_basis == "반경" else "시군구인구"
            density_txt = (
                f" [{density_per_10k}개/만명({basis_lbl}) · 전국 {nat_density}개/만명 대비 {vs_national_pct}%]"
            )
        else:
            density_txt = ""

        dscope = fact.get("scope")
        dscope_txt = f", {dscope} 기준" if dscope else ""
        note = (
            f"{r['demand_item']} {fact['value']}{unit}({nat_txt}{dscope_txt}) · "
            f"반경 {radius}m {'·'.join(r['supply_kinds'])} {count}개{density_txt}{cap_txt} — {verdict}"
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
                    scope=dscope,
                    scope_level=fact.get("scope_level"),
                ),
                supply=SupplySignal(
                    kinds=r["supply_kinds"], count=count, radius=radius, level=slevel,
                    density_per_10k=density_per_10k,
                    national_density_per_10k=nat_density,
                    vs_national_pct=vs_national_pct,
                    density_basis=density_basis,
                    capacity=capacity, capacity_scope=cap_scope,
                ),
                signal=f"수요 {dlevel}·공급 {slevel}",
                note=note,
                tag=r.get("tag", "참고"),
            )
        )
    return diagnoses, notes


def _collect_capacity(
    rules: List[dict], sgg_code: str, region_name: str,
    cache: Optional[Cache], client: Optional[httpx.Client],
) -> tuple:
    """capacity_source 지정 규칙의 시군구 정원 수집 → ({규칙명:{capacity,scope}}, notes).

    현재 'childcare'(어린이집 정보공개포털 정원)만. graceful — 실패 시 해당 규칙만 정원 생략.
    """
    capacity_data: dict = {}
    notes: List[str] = []
    needs_childcare = any(r.get("capacity_source") == "childcare" for r in rules)
    if needs_childcare:
        cc, ccnotes = childcare.fetch_childcare(
            sgg_code, region_name, cache=cache, client=client
        )
        notes += ccnotes
        if cc:
            for r in rules:
                if r.get("capacity_source") == "childcare":
                    capacity_data[r["name"]] = {
                        "capacity": cc["total_capacity"], "scope": cc["scope"]
                    }
    return capacity_data, notes


def build_diagnosis(
    address: str,
    radius: int = 1000,
    client: Optional[httpx.Client] = None,
    cache: Optional[Cache] = None,
    resolution: str = "시군구",
    use_type: Optional[str] = None,
) -> DiagnoseResult:
    """수급진단 결과 구성. demand facts 가 하나도 없으면 diagnoses 빈 배열(라우터가 ErrorBlock).

    resolution='읍면동'이면 동 데이터 있는 수요지표(유소년·고령 등)는 행정동 단위로 산정한다
    (공급은 항상 반경). 동 미지원 지표는 시군구로 폴백+note (절대 원칙 3·4).
    """
    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        loc = resolve_address(address, client=client)
        rules = load_rules()
        notes: List[str] = list(loc.notes)

        # P13 — 용도(프로파일) 관련 수급규칙만 (demand 지표·카카오 시설검색·진단이 줄어 API 절감).
        # 미지정·미등록이면 전체(하위호환). 전부 걸러지면 안전하게 전체 유지.
        from app.services.matrix import relevant_supply, resolve_profile
        allowed = relevant_supply(use_type)
        if allowed is not None:
            kept = [r for r in rules if r["name"] in allowed]
            if kept:
                dropped = [r["name"] for r in rules if r["name"] not in allowed]
                rules = kept
                if dropped:
                    notes.append(
                        f"용도({resolve_profile(use_type)}) 무관 수급규칙 {len(dropped)}개 제외 "
                        f"(관련 소스만 호출·P13): {', '.join(dropped)}."
                    )

        # 읍면동 요청이면 행정동 H코드 lazy 조회. 실패 시 구로 폴백.
        from app.services.kakao import coord_to_hdong
        hcode = hdong = ""
        if resolution == "읍면동":
            hd = coord_to_hdong(loc.lat, loc.lon, client=client)
            if hd and hd.get("code"):
                hcode, hdong = hd["code"], hd.get("name", "")
            else:
                notes.append("행정동 해석 실패 — 시군구 기준으로 폴백.")

        # demand: 규칙들의 distinct demand_item 모아 1세트 호출 (기준은 fact.scope — 절대 원칙 4)
        # KOSIS는 시군구/읍면동만 — '반경'은 baseline(시군구, national_avg 확보)을 먼저 받고 아래서 SGIS로 덮어씀.
        kosis_res = "시군구" if resolution == "반경" else resolution
        demand_items = list(dict.fromkeys(r["demand_item"] for r in rules))
        facts, dnotes, year = stats.collect_facts_by_items(
            loc.sgg_code, demand_items, sigungu=loc.sigungu, cache=cache,
            resolution=kosis_res, hcode=hcode, hdong=hdong,
        )
        notes += dnotes

        # 반경 모드: SGIS 집계구 합산으로 demand를 진짜 반경 인구비율로 교체 (수요·공급 동일 반경)
        radius_ok = False
        radius_pop: Optional[int] = None
        if resolution == "반경":
            from app.services import sgis
            try:
                rp = sgis.fetch_radius_population(loc.lat, loc.lon, radius, cache=cache, client=client)
            except Exception as e:  # noqa: BLE001 — graceful (절대 원칙 3)
                rp = None
                notes.append(f"SGIS 반경 인구 조회 오류: {e}")
            if rp:
                radius_ok = True
                radius_pop = rp.get("total_pop")  # 공급 밀도 분모(반경 1인당) — primary 판정용
                share_map = {
                    "유소년인구비율": rp.get("youth_share"),
                    "고령인구비율": rp.get("aged_share"),
                    "생산가능인구비율": rp.get("working_share"),
                }
                scope = f"반경 {radius}m"
                for f in facts:
                    sv = share_map.get(f["item"])
                    if sv is not None:
                        f["value"] = sv          # national_avg 는 KOSIS 전국값 유지 (비교 일관)
                        f["scope"] = scope
                        f["scope_level"] = "반경"
                        f["source_tbl"] = "SGIS 집계구"
                        f["year"] = int(rp.get("base_year", year or 0) or 0)
                    elif f["item"] not in share_map:
                        notes.append(f"'{f['item']}': SGIS 집계구 미제공 → {loc.sigungu} 기준.")
                notes += rp.get("notes", [])
            else:
                notes.append("SGIS 반경 인구 미확보 — 수요는 시군구 기준으로 폴백.")

        fact_by_item = {f["item"]: f for f in facts}

        # supply: 규칙들의 모든 시설종류를 한 번에 반경검색 (모드 B 재사용)
        kinds = list(dict.fromkeys(k for r in rules for k in r["supply_kinds"]))
        fres = build_facility_result(address, kinds, [radius], client=client, loc=loc)
        band = fres.counts.get(str(radius), {})
        notes += [n for n in fres.notes if n not in notes]

        # 시군구 정원 보강 (어린이집 정보공개포털 — 반경 개수와 단위 다름, 참고)
        capacity_data, capnotes = _collect_capacity(
            rules, loc.sgg_code, loc.sigungu, cache, client
        )
        notes += capnotes

        # 시군구 총인구 — 밀도 계산용 (DT_1B04005N 캐시 재사용, 추가 API 호출 없음)
        total_pop = fetch_total_pop(loc.sgg_code, cache=cache)

        diagnoses, cnotes = cross_rules(
            fact_by_item, band, radius, rules,
            capacity_data=capacity_data,
            total_pop=total_pop,
            radius_pop=radius_pop,
        )
        notes += cnotes

        # region: 수요 산정 단위 표기 (반경 > 읍면동 > 시군구). facts 의 scope_level 로 실제 달성 확인.
        dong_ok = hcode and any(f.get("scope_level") == "읍면동" for f in facts)
        if radius_ok:
            region = Region(
                name=f"{loc.sigungu or loc.sgg_code} 반경 {radius}m",
                code=loc.sgg_code, resolution="반경",
            )
        elif dong_ok:
            region = Region(name=hdong or "행정동", code=hcode, resolution="읍면동")
        else:
            region = Region(
                name=loc.sigungu or loc.sgg_code, code=loc.sgg_code, resolution="시군구"
            )

        return DiagnoseResult(
            center=Center(lat=loc.lat, lon=loc.lon, address=loc.address),
            region=region,
            radius=radius,
            diagnoses=diagnoses,
            source="kakao+kosis",
            base_date=date.today().isoformat(),
            notes=notes,
        )
    finally:
        if own:
            client.close()
