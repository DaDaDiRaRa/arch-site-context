"""T2 — 설계 드라이버 합성 엔진 (CLAUDE.md §8.12).

통합 풀(인구 지수 + 수급 signal + 재해)을 읽어 driver_rules.json 의 드라이버들을 **증거 강도로
랭킹**하고 상위 2~3개를 반환한다. "이 대지를 알고 나면 설계는 무엇에 응답해야 하나"의 답.

원칙:
- **LLM 0 · 새 숫자 안 만듦** — 기존 값(fact.index·supply.level·hazard.in_zone)을 가중합만 (절대 원칙 1·2).
- 드라이버는 '검토 신호'이지 판정·제안안이 아님 — 최종 설계 판단은 사람 (절대 원칙 5).
- 각 근거에 값·근접도(S1) 인용 — 투명 (절대 원칙 4).
- 설정은 JSON — 규칙·가중치·임계는 driver_rules.json 만 고치면 바뀐다 (절대 원칙 7).

S2(cross_context)와 어휘(signal 종류)를 공유하되 목적이 다르다 — cross_context 는 boolean AND 로
'참고 시사점' 문장, T2 는 가중 strength 로 드라이버 랭킹. build_board 가 둘 다 호출.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional, Tuple

from app.schemas.design_drivers import DesignDriver, DriverEvidence

_PATH = Path(__file__).resolve().parent.parent / "data" / "driver_rules.json"


def _load() -> dict:
    if not _PATH.exists():
        return {}
    return json.loads(_PATH.read_text(encoding="utf-8"))


# ── 값 추출 (dict / pydantic 공용) ───────────────────────────────────────────

def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _prox_weight(weights: dict, proximity: Optional[str]) -> float:
    return float((weights.get("proximity") or {}).get(proximity or "", 1.0))


# ── signal 평가기 — (matched, strength, DriverEvidence|None) ─────────────────

def _eval_signal(sig: dict, fact_by_item, diag_by_name, hazards, weights) -> Tuple[bool, float, Optional[DriverEvidence]]:
    # 인구 지수 (전국=100)
    if "pop" in sig:
        f = fact_by_item.get(sig["pop"])
        if f is None:
            return False, 0.0, None
        idx = _get(f, "index")
        if idx is None:
            return False, 0.0, None  # 비율 아님·비교불가 → 기여 없음 (추정 안 함)
        want = sig.get("dir", "high")
        band = _get(f, "index_band")
        if want == "high" and band != "상회":
            return False, 0.0, None
        if want == "low" and band != "하회":
            return False, 0.0, None
        mag = abs(idx - 100) / 10.0 * float(weights.get("pop_per_10pt", 1.0))
        s = mag * _prox_weight(weights, _get(f, "proximity"))
        unit = _get(f, "unit", "") or ""
        detail = f"{_get(f,'value')}{unit} (지수 {idx}·{band})"
        return True, s, DriverEvidence(key=sig["pop"], detail=detail, proximity=_get(f, "proximity"))

    # 수급 공급/수요 수준
    for side, wkey in (("supply", "supply_level"), ("demand", "demand_level")):
        if side in sig:
            d = diag_by_name.get(sig[side])
            if d is None:
                return False, 0.0, None
            signal = _get(d, side)
            level = _get(signal, "level")
            if level != sig.get("level"):
                return False, 0.0, None
            s = float(weights.get(wkey, 1.0)) * _prox_weight(weights, _get(signal, "proximity"))
            if side == "supply":
                kinds = _get(signal, "kinds") or []
                detail = f"공급 {level} ({'·'.join(kinds)} {_get(signal,'count')}개)"
                key = f"{sig['supply']}(공급)"
            else:
                detail = f"수요 {level} ({_get(signal,'item')} {_get(signal,'value')}{_get(signal,'unit','') or ''})"
                key = f"{sig['demand']}(수요)"
            return True, s, DriverEvidence(key=key, detail=detail, proximity=_get(signal, "proximity"))

    # 재해 영향범위 포함
    if "hazard" in sig:
        zone = _get(hazards, sig["hazard"])
        iz = _get(zone, "in_zone")
        if iz is None or bool(iz) != bool(sig.get("in_zone", True)):
            return False, 0.0, None
        label = "홍수" if sig["hazard"] == "flood" else "산사태"
        from app.schemas.proximity import proximity_of
        prox = proximity_of(_get(zone, "exposure_scope") or "") or "읍면동"
        return True, float(weights.get("hazard_zone", 3.0)), DriverEvidence(
            key=f"{label} 위험", detail="영향범위 포함", proximity=prox)

    # 영향범위 내 지표 (지하건물 등)
    if "hazard_exposure" in sig:
        zone = _get(hazards, sig["hazard_exposure"])
        exps = _get(zone, "exposures") or []
        metric = sig["metric"]
        match = next((e for e in exps if _get(e, "metric") == metric), None)
        aff = _get(match, "affected")
        if aff is None or float(aff) <= 0:
            return False, 0.0, None
        from app.schemas.proximity import proximity_of
        label = "홍수" if sig["hazard_exposure"] == "flood" else "산사태"
        prox = proximity_of(_get(zone, "exposure_scope") or "") or "읍면동"
        return True, float(weights.get("hazard_exposure", 1.0)), DriverEvidence(
            key=f"{label} 영향 {metric}", detail=f"{aff}{_get(match,'unit','') or ''}", proximity=prox)

    # 폭염특보 이력
    if "heatwave" in sig:
        hw = _get(hazards, "heatwave")
        val = _get(hw, sig["heatwave"])
        if val is None or float(val) < float(sig.get("min", 0)):
            return False, 0.0, None
        scope = _get(hw, "scope", "") or ""
        prox = "proxy" if "광역" in scope else "시군구"
        label = "폭염경보" if sig["heatwave"] == "alert_count" else "폭염주의보"
        return True, float(weights.get("heatwave", 1.5)), DriverEvidence(
            key=label, detail=f"{val}건 ({scope})", proximity=prox)

    return False, 0.0, None


def derive_design_drivers(
    facts: Optional[List[Any]] = None,
    diagnoses: Optional[List[Any]] = None,
    hazards: Any = None,
    use_type: Optional[str] = None,
) -> List[DesignDriver]:
    """통합 풀 → 지배 설계 드라이버 상위 N개 (증거 강도 랭킹). 근거 없으면 빈 리스트."""
    facts = facts or []
    diagnoses = diagnoses or []
    rules = _load()
    weights = rules.get("weights", {})
    min_strength = float(rules.get("min_strength", 1.0))
    max_drivers = int(rules.get("max_drivers", 3))

    fact_by_item = {_get(f, "item"): f for f in facts if _get(f, "item")}
    diag_by_name = {_get(d, "name"): d for d in diagnoses if _get(d, "name")}

    from app.services.matrix import resolve_profile
    profile = resolve_profile(use_type) if use_type is not None else None  # 법적 용도 → 프로파일 (2계층)
    candidates: List[Tuple[float, dict, List[DriverEvidence]]] = []
    for rule in rules.get("drivers", []):
        uses = rule.get("use_types") or []
        if profile is not None and uses and profile not in uses:
            continue
        strength = 0.0
        evidence: List[DriverEvidence] = []
        for sig in rule.get("signals", []):
            matched, s, ev = _eval_signal(sig, fact_by_item, diag_by_name, hazards, weights)
            if matched:
                strength += s
                if ev is not None:
                    evidence.append(ev)
        if evidence and strength >= min_strength:
            candidates.append((strength, rule, evidence))

    candidates.sort(key=lambda c: c[0], reverse=True)
    out: List[DesignDriver] = []
    for rank, (strength, rule, evidence) in enumerate(candidates[:max_drivers], start=1):
        out.append(DesignDriver(
            rank=rank,
            name=rule.get("name", ""),
            response=rule.get("then") or rule.get("response", ""),
            strength=round(strength, 2),
            evidence=evidence,
            tag=rule.get("tag", "참고"),
        ))
    return out
