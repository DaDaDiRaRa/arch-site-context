"""T5 — 방법론·데이터 부록 엔진 (CLAUDE.md §8.12).

BoardResult 에 이미 흐르는 출처(source_tbl·source·presence)를 모아 "이 수치가 어디서·어떻게"
나왔는지 자동 부록으로 각인한다. 공공 공모·감사 대비 (절대 원칙 4). **LLM 0·새 숫자 0** —
새 데이터·계산 없음, 기존 출처 메타데이터를 레지스트리(methodology.json)와 조인할 뿐.

원칙: **기여한 출처만** 담는다(no silent inclusion). 레지스트리에 없는 소스는 지어내지 않고
원시 키 + '미등록' note 로 정직하게 노출한다 (절대 원칙 3). 산정식·한계도 규칙으로만.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.methodology import FormulaEntry, Methodology, SourceEntry
from app.schemas.proximity import proximity_rank

_PATH = Path(__file__).resolve().parent.parent / "data" / "methodology.json"


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


def _match_source(source_tbl: Optional[str], source_type: Optional[str], reg: dict) -> str:
    """fact 의 source_tbl/source_type → 레지스트리 정규 키. 없으면 원시 키 (지어내지 않음)."""
    st = (source_tbl or "").strip()
    if st and st in reg:
        return st
    for key, meta in reg.items():
        for m in meta.get("match", []):
            if (st and st.startswith(m)) or (source_type and source_type == m):
                return key
    return st or (source_type or "미상")


def _best_prox(proxes: List[str]) -> Optional[str]:
    """여러 근접도 중 가장 대지에 가까운(최상급) 하나. 없으면 None."""
    vals = [p for p in proxes if p]
    if not vals:
        return None
    return min(vals, key=proximity_rank)


def _present_domains(board: Any) -> List[str]:
    """이 보드에 실제로 채워진 도메인 키 (presence 기반 출처 결정용). no silent skip 은 유지."""
    doms: List[str] = []
    if _g(board, "diagnoses"):
        doms.append("facilities")  # 공급 = 반경 시설검색
    haz = _g(board, "hazards")
    if haz and (
        (_g(_g(haz, "flood"), "in_zone") is not None)
        or (_g(_g(haz, "landslide"), "in_zone") is not None)
    ):
        doms.append("hazards")
    lp = _g(board, "land_price")
    if lp and _g(lp, "price_per_sqm") is not None:
        doms.append("land_price")
    bld = _g(board, "building")
    if bld and _g(bld, "name"):
        doms.append("building")
    re = _g(board, "real_estate")
    if re and _g(re, "transactions"):
        doms.append("real_estate")
    ctx = _g(board, "context") or {}
    for k, v in ctx.items():
        if k == "notes" or not v:
            continue
        doms.append(k)
    return doms


def _summary(resolution: str, n_src: int, n_formula: int) -> str:
    return (
        f"이 보드의 모든 수치는 실제 API 호출로 수집했고 출처·기준연도를 각인했습니다. "
        f"인구/수요 산정 단위는 '{resolution}'이며, 데이터 출처 {n_src}종·산정식 {n_formula}건을 "
        f"아래에 명시합니다. 수치는 코드·규칙이 만들고 표현만 AI가 담당합니다 (새 숫자 0)."
    )


def _limitations(board: Any, resolution: str) -> List[str]:
    """한계·주의 — 평균값 캐비엇 + 확인불가 도메인 + 휴리스틱. 숨기지 않음 (절대 원칙 3·4·5)."""
    lims: List[str] = []
    if resolution == "반경":
        lims.append(
            "반경 인구는 SGIS 집계구 실측 합산이나, 가구·대기질 등 시군구 지표는 여전히 구 평균 — "
            "각 수치의 근접도 등급 참조."
        )
    else:
        lims.append(
            f"인구·통계는 {resolution} 평균값으로 대지 고유값이 아님 — 각 수치의 근접도 등급 참조 (절대 원칙 4)."
        )
    for c in _g(board, "coverage") or []:
        if not _g(c, "available"):
            lims.append(f"{_g(c, 'domain')} 도메인 확인 불가: {_g(c, 'detail')}")
    if _g(board, "diagnoses"):
        lims.append("수급진단의 부족/과잉은 휴리스틱 — '참고'이며 최종 판단은 사람 (절대 원칙 5).")
    return lims


def build_methodology(board: Any) -> Methodology:
    """BoardResult(또는 model_dump dict) → Methodology 부록. 기여한 출처·등장한 산정식만."""
    reg = _load()
    sources_reg: dict = reg.get("sources", {})
    formulas_reg: dict = reg.get("formulas", {})
    domain_map: dict = reg.get("domain_sources", {})

    facts = _g(board, "facts") or []
    diagnoses = _g(board, "diagnoses") or []
    resolution = _g(board, "resolution") or "시군구"
    base_date = _g(board, "base_date") or ""

    # 1) fact/수요 기반 출처 사용 집계 (등장 순서 보존)
    usage: Dict[str, dict] = {}
    order: List[str] = []

    def _touch(key: str, item: Optional[str] = None, year: Any = None, prox: Optional[str] = None) -> None:
        if key not in usage:
            usage[key] = {"items": [], "years": [], "prox": []}
            order.append(key)
        u = usage[key]
        if item and item not in u["items"]:
            u["items"].append(item)
        if year is not None and year not in u["years"]:
            u["years"].append(year)
        if prox and prox not in u["prox"]:
            u["prox"].append(prox)

    for f in facts:
        key = _match_source(_g(f, "source_tbl"), _g(f, "source_type"), sources_reg)
        _touch(key, _g(f, "item"), _g(f, "year"), _g(f, "proximity"))

    for d in diagnoses:
        dem = _g(d, "demand")
        if dem:
            key = _match_source(_g(dem, "source_tbl"), None, sources_reg)
            _touch(key, _g(dem, "item"), _g(dem, "year"), _g(dem, "proximity"))

    # 2) presence 기반 도메인 출처 (재해·대지·생활맥락 — fact 를 안 거치는 것)
    for dom in _present_domains(board):
        for key in domain_map.get(dom, []):
            _touch(key)

    # 3) SourceEntry 조립 (기여한 것만 — no silent inclusion)
    sources: List[SourceEntry] = []
    for key in order:
        meta = sources_reg.get(key, {})
        u = usage[key]
        used = list(u["items"]) or list(meta.get("used_for", []))
        note = "" if key in sources_reg else "출처 상세 미등록 (methodology.json 보강 대상)."
        sources.append(SourceEntry(
            key=key,
            name=meta.get("name", key),
            publisher=meta.get("publisher", ""),
            api=meta.get("api", ""),
            kind=meta.get("kind", ""),
            used_for=used,
            years=sorted(u["years"]),
            proximity=_best_prox(u["prox"]),
            note=note,
        ))

    # 4) 산정식 — 등장한 파생 지표 + 조건부 횡단 산정식만
    formulas: List[FormulaEntry] = []
    seen: set = set()

    def _add(label: str) -> None:
        if label in formulas_reg and label not in seen:
            seen.add(label)
            fr = formulas_reg[label]
            formulas.append(FormulaEntry(item=label, formula=fr.get("formula", ""), note=fr.get("note", "")))

    for f in facts:
        _add(_g(f, "item"))
    if any(_g(f, "index") is not None for f in facts):
        _add("전국=100 지수")
    if resolution == "반경":
        _add("반경 인구")
        _add("반경 연령비율")
    if any(_g(_g(d, "supply"), "density_basis") == "반경" for d in diagnoses):
        _add("공급 밀도(만명당)")

    # 5) 한계 + 요약
    limitations = _limitations(board, resolution)
    summary = _summary(resolution, len(sources), len(formulas))

    return Methodology(
        summary=summary,
        resolution=resolution,
        sources=sources,
        formulas=formulas,
        limitations=limitations,
        base_date=base_date,
    )
