"""모드A 밀도정규화 (§8.6) — census 다차원 count 를 인구당(천명당)으로 정규화한 facts.

raw count(사업체 96,993개)를 전국 총량과 비교하는 건 무의미 → 시군구 count/시군구인구 vs
전국 count/전국인구(둘 다 per-천명)로 정규화해 /analyze 의 national_avg·지수 모델에 맞춘다.
전국 census 는 크랙 엔진(census_multidim)이 region '전국' 멤버로 해석(하드코딩 0, 절대 원칙 1).

값은 실제 KOSIS (절대 원칙 1). 시군구 단위·참고(절대 원칙 4). 실패는 graceful — 건너뜀+notes(원칙 3).
opt-in: /analyze density=true 일 때만 (census 크랙 호출이라 다소 느림). 국가코드·전국 캐시로 재호출 절감.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

import httpx

from app.services import census_multidim
from app.services.cache import Cache
from app.services.stats import fetch_total_pop

_PATH = Path(__file__).resolve().parent.parent / "data" / "census_density.json"
_NATIONAL_CODE = "00"  # DT_1B04005N 국가(전국) 코드 — 총인구 분모


def _load() -> dict:
    if not _PATH.exists():
        return {}
    return json.loads(_PATH.read_text(encoding="utf-8"))


def _year(v) -> Optional[int]:
    try:
        return int(str(v)[:4]) if v else None
    except (ValueError, TypeError):
        return None


def collect_density_facts(
    sgg_code: str,
    sigungu: str,
    sido: str,
    use_type: str,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[List[dict], List[str]]:
    """용도(프로파일)별 census 밀도 facts (per-천명 + 동적 전국 벤치마크).

    Returns (facts[dict], notes). facts 는 /analyze 가 Fact(**f)로 병합 → 지수 자동 유도.
    """
    from app.services.matrix import resolve_profile

    profile = resolve_profile(use_type)
    inds = _load().get("indicators", {}).get(profile or "", [])
    if not inds:
        return [], []

    sgg_pop = fetch_total_pop(sgg_code, cache=cache)
    nat_pop = fetch_total_pop(_NATIONAL_CODE, cache=cache)
    if not sgg_pop or not nat_pop:
        return [], ["census 밀도: 인구 분모(시군구·전국) 미확보 — 건너뜀."]

    facts: List[dict] = []
    notes: List[str] = []
    own = client is None
    client = client or httpx.Client(timeout=25.0)
    try:
        for ind in inds:
            sgg_d, n1 = census_multidim.fetch_census_indicator(
                ind["org"], ind["tbl"], ind["itm"], sigungu, ind["prd"],
                sido=sido, cache=cache, client=client,
            )
            nat_d, _n2 = census_multidim.fetch_census_indicator(
                ind["org"], ind["tbl"], ind["itm"], "전국", ind["prd"],
                sido="", cache=cache, client=client,
            )
            notes += n1
            if not (sgg_d and sgg_d.get("value") is not None
                    and nat_d and nat_d.get("value") is not None):
                notes.append(f"{ind['item']}: census 값 미확보 — 건너뜀.")
                continue
            facts.append({
                "item": ind["item"],
                "value": round(sgg_d["value"] / sgg_pop * 1000, 1),
                "national_avg": round(nat_d["value"] / nat_pop * 1000, 1),
                "unit": ind["unit"],
                "source_tbl": ind["tbl"],
                "year": _year(sgg_d.get("year")),
                "source_type": "census_density",
                "scope": sigungu,
                "scope_level": "시군구",
            })
    finally:
        if own:
            client.close()
    return facts, notes
