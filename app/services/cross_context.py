"""S2 — 교차규칙 엔진 (CLAUDE.md §8.11).

통합 fact 풀(인구 facts + 수급진단 signal + 재해)을 읽어, cross_context.json 규칙의
조건 절이 **모두** 참일 때만 도메인 횡단 '참고' 시사점을 만든다.

원칙:
- **LLM 0 · 새 숫자 안 만듦** — 기존 값을 boolean 조합하고 basis 에 그대로 인용만 (절대 원칙 1·2).
- **확인 불가면 멈춤** — 비교 기준(national_avg)·지표가 없으면 그 절은 불충족 처리, 추정 안 함 (절대 원칙 3).
- **근접도 인용** — 각 basis 에 S1 proximity 를 실어 근거의 대지 근접도를 투명하게 (절대 원칙 4).
- **설정은 JSON** — 규칙은 cross_context.json 만 고치면 바뀐다 (절대 원칙 7).

S2 는 순수 엔진이다. 통합 풀을 조립해 이 엔진을 호출하는 것은 S3(/board)의 몫.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

from app.schemas.cross_context import CrossBasis, CrossImplication
from app.schemas.proximity import proximity_of

_PATH = Path(__file__).resolve().parent.parent / "data" / "cross_context.json"

# 절 종류 → 도메인 (domains 자동 유도, 규칙 편집자가 따로 안 적어도 됨)
_CLAUSE_DOMAIN = {
    "pop": "인구",
    "supply": "수급",
    "demand": "수급",
    "hazard": "재해",
    "hazard_exposure": "재해",
    "heatwave": "재해",
}

# 폭염특보 구역은 최소 시군구, 광역 권역이면 그보다 넓음
_HEATWAVE_METRIC = {"alert_count": "폭염경보", "warning_count": "폭염주의보"}


def load_rules() -> List[dict]:
    """cross_context.json 규칙 배열. 없으면 빈 리스트."""
    if not _PATH.exists():
        return []
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    return data.get("rules", [])


# ─────────────────────────────────────────────────────────────────────────────
# 값 추출 헬퍼 (dict / pydantic 모델 공용)
# ─────────────────────────────────────────────────────────────────────────────

def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _passes(value: float, threshold: float, op: str) -> bool:
    if op == ">":
        return value > threshold
    if op == ">=":
        return value >= threshold
    if op == "<":
        return value < threshold
    if op == "<=":
        return value <= threshold
    return False


def _as_list(v: Any) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


# ─────────────────────────────────────────────────────────────────────────────
# 절(clause) 평가기 — 각각 (matched, CrossBasis|None) 반환
# ─────────────────────────────────────────────────────────────────────────────

def _eval_pop(clause: dict, fact_by_item: dict):
    fact = fact_by_item.get(clause["pop"])
    if fact is None:
        return False, None
    value = _get(fact, "value")
    if value is None:
        return False, None
    op = clause.get("op", ">")
    unit = _get(fact, "unit", "") or ""
    if "value" in clause:  # 절대값 비교
        threshold = float(clause["value"])
        detail = f"{value}{unit} (기준 {clause['value']}{unit})"
    else:  # 전국 대비
        base = _get(fact, "national_avg")
        if base is None:
            return False, None  # 비교 기준 없으면 추정 안 함 (절대 원칙 3)
        margin = float(clause.get("margin", 0))
        threshold = base + margin if op in (">", ">=") else base - margin
        detail = f"{value}{unit} (전국 {base}{unit})"
    if not _passes(float(value), threshold, op):
        return False, None
    return True, CrossBasis(
        key=clause["pop"], detail=detail, proximity=_get(fact, "proximity")
    )


def _eval_diag(clause: dict, diag_by_name: dict, side: str):
    """side = 'supply' | 'demand'."""
    diag = diag_by_name.get(clause[side])
    if diag is None:
        return False, None
    signal = _get(diag, side)  # SupplySignal | DemandSignal
    level = _get(signal, "level")
    if level is None or level not in _as_list(clause.get("level")):
        return False, None
    if side == "supply":
        kinds = _get(signal, "kinds") or []
        count = _get(signal, "count")
        detail = f"공급 {level} ({'·'.join(kinds)} {count}개)"
        key = f"{clause['supply']}(공급)"
    else:
        val = _get(signal, "value")
        unit = _get(signal, "unit", "") or ""
        nat = _get(signal, "national_avg")
        nat_txt = f", 전국 {nat}{unit}" if nat is not None else ""
        detail = f"수요 {level} ({_get(signal, 'item')} {val}{unit}{nat_txt})"
        key = f"{clause['demand']}(수요)"
    return True, CrossBasis(key=key, detail=detail, proximity=_get(signal, "proximity"))


def _zone(hazards: Any, name: str):
    """hazards.flood / hazards.landslide 추출."""
    return _get(hazards, name)


def _eval_hazard(clause: dict, hazards: Any):
    zone = _zone(hazards, clause["hazard"])
    if zone is None:
        return False, None
    in_zone = _get(zone, "in_zone")
    if in_zone is None:  # 확인불가 → 멈춤 (절대 원칙 3)
        return False, None
    if bool(in_zone) != bool(clause.get("in_zone", True)):
        return False, None
    label = "홍수" if clause["hazard"] == "flood" else "산사태"
    state = "영향범위 포함" if in_zone else "영향범위 외"
    scope = _get(zone, "exposure_scope") or ""
    return True, CrossBasis(
        key=f"{label} 위험", detail=state, proximity=proximity_of(scope) or "읍면동"
    )


def _eval_hazard_exposure(clause: dict, hazards: Any):
    zone = _zone(hazards, clause["hazard_exposure"])
    if zone is None:
        return False, None
    metric = clause["metric"]
    exposures = _get(zone, "exposures") or []
    match = None
    for e in exposures:
        if _get(e, "metric") == metric:
            match = e
            break
    if match is None:
        return False, None
    affected = _get(match, "affected")
    if affected is None:
        return False, None
    op = clause.get("op", ">")
    if not _passes(float(affected), float(clause.get("value", 0)), op):
        return False, None
    unit = _get(match, "unit", "") or ""
    scope = _get(zone, "exposure_scope") or ""
    label = "홍수" if clause["hazard_exposure"] == "flood" else "산사태"
    # 노출 지표는 exposure_scope 가 읍면동 또는 시군구 폴백(§8.10) — scope 불명 시 보수적으로 시군구
    # (근접도 과대표기 방지, CLAUDE.md 함정: 근접도가 거짓이면 차별점 붕괴)
    return True, CrossBasis(
        key=f"{label} 영향 {metric}",
        detail=f"{affected}{unit}",
        proximity=proximity_of(scope) or "시군구",
    )


def _eval_heatwave(clause: dict, hazards: Any):
    hw = _get(hazards, "heatwave")
    if hw is None:
        return False, None
    field = clause["heatwave"]
    val = _get(hw, field)
    if val is None:
        return False, None
    op = clause.get("op", ">=")
    if not _passes(float(val), float(clause.get("value", 0)), op):
        return False, None
    scope = _get(hw, "scope") or ""
    label = _HEATWAVE_METRIC.get(field, field)
    # 폭염특보 구역은 시군구~광역 권역 — 광역이면 대지에서 먼 근사
    prox = "proxy" if "광역" in scope else "시군구"
    return True, CrossBasis(key=label, detail=f"{val}건 ({scope})", proximity=prox)


# ─────────────────────────────────────────────────────────────────────────────
# 엔진
# ─────────────────────────────────────────────────────────────────────────────

def _eval_clause(clause: dict, fact_by_item, diag_by_name, hazards):
    """절 1개 평가 → (matched, CrossBasis|None). 알 수 없는 절 종류는 불충족."""
    if "pop" in clause:
        return _eval_pop(clause, fact_by_item)
    if "supply" in clause:
        return _eval_diag(clause, diag_by_name, "supply")
    if "demand" in clause:
        return _eval_diag(clause, diag_by_name, "demand")
    if "hazard" in clause:
        return _eval_hazard(clause, hazards)
    if "hazard_exposure" in clause:
        return _eval_hazard_exposure(clause, hazards)
    if "heatwave" in clause:
        return _eval_heatwave(clause, hazards)
    return False, None


def _clause_domain(clause: dict) -> Optional[str]:
    for k, dom in _CLAUSE_DOMAIN.items():
        if k in clause:
            return dom
    return None


def derive_cross_context(
    facts: Optional[List[Any]] = None,
    diagnoses: Optional[List[Any]] = None,
    hazards: Any = None,
    use_type: Optional[str] = None,
) -> List[CrossImplication]:
    """통합 fact 풀에 교차규칙을 적용해 '참고' 시사점 리스트 반환.

    facts: 인구 facts (Fact 또는 dict). diagnoses: 수급진단(Diagnosis 또는 dict).
    hazards: SiteHazards(또는 dict). use_type 지정 시 규칙 use_types 필터(빈 목록=모든 용도).
    어느 절이라도 불충족이면 규칙 미발화 — 확인 불가는 추정 않고 멈춤 (절대 원칙 3).
    """
    facts = facts or []
    diagnoses = diagnoses or []

    fact_by_item: dict = {}
    for f in facts:
        item = _get(f, "item")
        if item is not None:
            fact_by_item[item] = f
    diag_by_name: dict = {}
    for d in diagnoses:
        name = _get(d, "name")
        if name is not None:
            diag_by_name[name] = d

    from app.services.matrix import resolve_profile
    profile = resolve_profile(use_type) if use_type is not None else None  # 법적 용도 → 프로파일 (2계층)
    out: List[CrossImplication] = []
    for rule in load_rules():
        uses = rule.get("use_types") or []
        if profile is not None and uses and profile not in uses:
            continue

        clauses = rule.get("when") or []
        if not clauses:
            continue

        basis: List[CrossBasis] = []
        domains: List[str] = []
        ok = True
        for clause in clauses:
            matched, b = _eval_clause(clause, fact_by_item, diag_by_name, hazards)
            if not matched:
                ok = False
                break
            if b is not None:
                basis.append(b)
            dom = _clause_domain(clause)
            if dom and dom not in domains:
                domains.append(dom)
        if not ok:
            continue

        out.append(
            CrossImplication(
                name=rule.get("name", ""),
                text=rule.get("then", ""),
                basis=basis,
                domains=domains,
                tag=rule.get("tag", "참고"),
            )
        )
    return out
