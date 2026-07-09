"""T 시리즈 2단계 — /board 를 형제앱 공유 계약으로 확정 (INTEGRATION.md §4).

터읽기는 provider — 형제를 호출하지 않는다. 대신 /board 결과를 **안정된 계약**으로 노출해
소비자(competition·MCP·kw-ai-hub 파이프라인·site-model)가 붙게 한다.

두 산출:
- `board_to_project_seed` : /board(BoardResult) → 세 앱 공유 `ProjectSeed` 봉투. context=터읽기 블록,
  law·knowledge 는 형제앱 자리(빈 슬롯). 조립 파이프라인·site-model 결합용.
- `board_brief` : /board → **제안서·프롬프트·MCP 반환용 압축 투영**(~66KB → ~수KB). 원시 seed context
  (상권 수천건 목록 등)·건물 상세를 걷어내고 해석 층(지수·수급·재해·교차·드라이버·종합)만 남긴다.

★ 경계(INTEGRATION §2): brief 는 사실·드라이버·①사실종합·②AI판단을 모두 담되, **competition 등 소비자는
제안서에 ②AI판단을 그대로 옮기지 않는다**(이중 AI 의견·출처 흐림 방지) — 사실+드라이버+①까지가 권장.
계약은 정책을 강제하지 않고 투영만 — 사용 경계는 문서(§2)가 정한다.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.schemas.project_seed import ProjectSeed, Site


def _g(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _dump(obj: Any) -> Any:
    """pydantic 모델·리스트·dict 를 순수 dict/list 로."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_dump(x) for x in obj]
    return obj


def board_to_project_seed(
    board: Any, law: Optional[dict] = None, knowledge: Optional[dict] = None,
) -> ProjectSeed:
    """BoardResult → ProjectSeed 봉투. context=터읽기 전체 블록, law·knowledge=형제앱 자리."""
    site = _g(board, "site")
    site_obj = site if isinstance(site, Site) else Site(**_dump(site)) if site else None
    context = board.model_dump() if hasattr(board, "model_dump") else dict(board)
    base = _g(board, "base_date") or date.today().isoformat()
    return ProjectSeed(site=site_obj, context=context, law=law, knowledge=knowledge, base_date=base)


def _hazard_brief(hazards: Any) -> Optional[dict]:
    if hazards is None:
        return None
    flood, land = _g(hazards, "flood"), _g(hazards, "landslide")
    hw = _g(hazards, "heatwave")
    return {
        "flood_in_zone": _g(flood, "in_zone"),
        "landslide_in_zone": _g(land, "in_zone"),
        "flood_exposures": [
            {"metric": _g(e, "metric"), "affected": _g(e, "affected"), "unit": _g(e, "unit", "")}
            for e in (_g(flood, "exposures") or [])
        ],
        "heatwave_alerts": _g(hw, "alert_count") if hw is not None else None,
        "heatwave_warnings": _g(hw, "warning_count") if hw is not None else None,
    }


def board_brief(board: Any) -> dict:
    """제안서·프롬프트·MCP 반환용 압축 투영. 해석 층만 (원시 seed context·건물 상세 제외)."""
    site = _g(board, "site")
    region = _g(board, "region")
    facts = _g(board, "facts") or []
    land = _g(board, "land_price")
    building = _g(board, "building")
    syn = _g(board, "synthesis")

    brief = {
        "schema_version": "board_brief/1.0",
        "site": {
            "address": _g(site, "address"), "sigungu": _g(site, "sigungu"),
            "eupmyeondong": _g(site, "eupmyeondong"), "sgg_code": _g(site, "sgg_code"),
            "pnu": _g(site, "pnu"), "lat": _g(site, "lat"), "lon": _g(site, "lon"),
        },
        "region": _g(region, "name") if region else None,
        "archetype": _dump(_g(board, "archetype")),  # ★ 동네 유형 (T1.5)
        "use_type": _g(board, "use_type"),
        "radius": _g(board, "radius"),
        "coverage": [{"domain": _g(c, "domain"), "available": _g(c, "available"),
                      "detail": _g(c, "detail")} for c in (_g(board, "coverage") or [])],
        # ★ 설계 드라이버 (T2) — 제안서 컨셉 방향의 핵심 재료
        "design_drivers": _dump(_g(board, "design_drivers")),
        # ★ 프로그램 함의 (T3) — 카테고리별 공간·프로그램 권고 (POR)
        "program_implications": _dump(_g(board, "program_implications")),
        # 교차 시사점 (S2)
        "cross_implications": [
            {"name": _g(c, "name"), "text": _g(c, "text"), "domains": _g(c, "domains"),
             "tag": _g(c, "tag")}
            for c in (_g(board, "cross_implications") or [])
        ],
        # 핵심 통계 (지수·근접도 부착) — 원시 값만, 지수 있는 것 우선
        "key_facts": [
            {"item": _g(f, "item"), "value": _g(f, "value"), "unit": _g(f, "unit"),
             "national_avg": _g(f, "national_avg"), "index": _g(f, "index"),
             "index_band": _g(f, "index_band"), "proximity": _g(f, "proximity"),
             "source": _g(f, "source_tbl"), "year": _g(f, "year")}
            for f in facts
        ],
        "hazards": _hazard_brief(_g(board, "hazards")),
        "land_price": {"price_per_sqm": _g(land, "price_per_sqm"), "year": _g(land, "year")} if land else None,
        "building": {"name": _g(building, "name"), "far": _g(building, "far"),
                     "bcr": _g(building, "bcr")} if building and _g(building, "name") else None,
        # 종합 (①사실 · ②AI의견 — ②는 제안서 직접전재 금지·§2 경계)
        "synthesis": {
            "interpretation": _g(syn, "interpretation"),
            "interpretation_source": _g(syn, "interpretation_source"),
            "judgment": _g(syn, "judgment"),
            "judgment_source": _g(syn, "judgment_source"),
            "judgment_label": _g(syn, "judgment_label"),
        } if syn else None,
        "base_date": _g(board, "base_date"),
        "notes": _g(board, "notes") or [],
    }
    return brief
