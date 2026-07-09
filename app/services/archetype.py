"""T1.5 — 대지 아키타입(동네 유형) 분류 엔진 (CLAUDE.md §8.12).

통합 풀(인구 facts + 수급 signal + 재해)을 archetype_rules.json 규칙과 매칭해 **지배 유형 1개**
(+ 차점 alternatives)를 라벨링한다. "이 동네는 ○○형" — Esri Tapestry legibility, 단 K-means 아닌
**결정론 규칙 룩업**(절대 원칙 1). 새 숫자 안 만듦 — 기존 지수·값·in_zone 임계 조합만 (원칙 2).

뚜렷한 지배 유형이 약하면 '혼합형' 폴백(억지 분류 금지, 원칙 3). 그라운딩 풀 자체가 없으면 None.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional, Tuple

from app.schemas.archetype import Archetype, ArchetypeEvidence
from app.schemas.proximity import proximity_of

_PATH = Path(__file__).resolve().parent.parent / "data" / "archetype_rules.json"


def _load() -> dict:
    if not _PATH.exists():
        return {}
    return json.loads(_PATH.read_text(encoding="utf-8"))


def _g(o: Any, k: str, d: Any = None) -> Any:
    if o is None:
        return d
    if isinstance(o, dict):
        return o.get(k, d)
    return getattr(o, k, d)


def _passes(v: float, t: float, op: str) -> bool:
    return {">": v > t, ">=": v >= t, "<": v < t, "<=": v <= t}.get(op, False)


# ── signal 평가 → (matched, weight, ArchetypeEvidence|None) ──────────────────

def _eval(sig: dict, fact_by_item, diag_by_name, hazards) -> Tuple[bool, float, Optional[ArchetypeEvidence]]:
    if "pop" in sig:
        f = fact_by_item.get(sig["pop"])
        band = _g(f, "index_band")
        if band is None:
            return False, 0.0, None
        want = sig.get("dir", "high")
        if (want == "high" and band != "상회") or (want == "low" and band != "하회"):
            return False, 0.0, None
        unit = _g(f, "unit", "") or ""
        return True, 1.0, ArchetypeEvidence(
            key=sig["pop"], detail=f"{_g(f,'value')}{unit} (지수 {_g(f,'index')}·{band})",
            proximity=_g(f, "proximity"))

    if "fact" in sig:
        f = fact_by_item.get(sig["fact"])
        val = _g(f, "value")
        if val is None:
            return False, 0.0, None
        op = sig.get("op", ">")
        if "value" in sig:
            thr = float(sig["value"])
        else:
            base = _g(f, "national_avg")
            if base is None:
                return False, 0.0, None
            m = float(sig.get("margin", 0))
            thr = base + m if op in (">", ">=") else base - m
        if not _passes(float(val), thr, op):
            return False, 0.0, None
        unit = _g(f, "unit", "") or ""
        return True, 1.0, ArchetypeEvidence(
            key=sig["fact"], detail=f"{val}{unit}", proximity=_g(f, "proximity"))

    if "hazard" in sig:
        zone = _g(hazards, sig["hazard"])
        iz = _g(zone, "in_zone")
        if iz is None or bool(iz) != bool(sig.get("in_zone", True)):
            return False, 0.0, None
        label = "홍수" if sig["hazard"] == "flood" else "산사태"
        prox = proximity_of(_g(zone, "exposure_scope") or "") or "읍면동"
        return True, 1.0, ArchetypeEvidence(key=f"{label} 위험", detail="영향범위 포함", proximity=prox)

    if "supply" in sig:
        d = diag_by_name.get(sig["supply"])
        signal = _g(d, "supply")
        if _g(signal, "level") != sig.get("level"):
            return False, 0.0, None
        kinds = _g(signal, "kinds") or []
        return True, 1.0, ArchetypeEvidence(
            key=f"{sig['supply']}(공급)", detail=f"{_g(signal,'level')} ({'·'.join(kinds)} {_g(signal,'count')}개)",
            proximity=_g(signal, "proximity"))

    return False, 0.0, None


def _has_pool(facts, diagnoses, hazards) -> bool:
    if facts or diagnoses:
        return True
    for key in ("flood", "landslide"):
        if _g(_g(hazards, key), "in_zone") is not None:
            return True
    return False


def classify_archetype(
    facts: Optional[List[Any]] = None,
    diagnoses: Optional[List[Any]] = None,
    hazards: Any = None,
    use_type: Optional[str] = None,
) -> Optional[Archetype]:
    """통합 풀 → 지배 동네 유형(+alternatives). 풀 없으면 None, 강한 매칭 없으면 '혼합형' 폴백."""
    facts = facts or []
    diagnoses = diagnoses or []
    if not _has_pool(facts, diagnoses, hazards):
        return None

    rules = _load()
    min_score = float(rules.get("min_score", 1.0))
    fact_by_item = {_g(f, "item"): f for f in facts if _g(f, "item")}
    diag_by_name = {_g(d, "name"): d for d in diagnoses if _g(d, "name")}

    candidates: List[Tuple[float, float, dict, List[ArchetypeEvidence]]] = []
    for arch in rules.get("archetypes", []):
        uses = arch.get("use_types") or []
        if use_type is not None and uses and use_type not in uses:
            continue
        sigs = arch.get("signals", [])
        score = 0.0
        matched = 0
        evidence: List[ArchetypeEvidence] = []
        for sig in sigs:
            ok, w, ev = _eval(sig, fact_by_item, diag_by_name, hazards)
            if ok:
                score += w
                matched += 1
                if ev is not None:
                    evidence.append(ev)
        ratio = matched / len(sigs) if sigs else 0
        if matched >= int(arch.get("min_match", 1)) and score >= min_score:
            candidates.append((score, ratio, arch, evidence))

    if not candidates:
        fb = rules.get("fallback") or {}
        return Archetype(name=fb.get("name", "혼합형 시가지"), group=fb.get("group", "혼합"),
                         description=fb.get("description", ""), match_score=0.0,
                         evidence=[], alternatives=[], tag=fb.get("tag", "참고"))

    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    score, _ratio, arch, evidence = candidates[0]
    alts = [c[2]["name"] for c in candidates[1:4]]
    return Archetype(
        name=arch["name"], group=arch["group"], description=arch["description"],
        match_score=round(score, 2), evidence=evidence, alternatives=alts,
        tag=arch.get("tag", "참고"),
    )
