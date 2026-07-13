"""심의 현황팩 — 조사범위 내 시설 현황 조사 (CLAUDE.md §8.13).

'조사범위 내 작은도서관/경로당/어린이집 현황' 표의 데이터. 반경 내 실시설 목록·개수를
카카오·VWorld·정보공개포털에서 수집 (절대 원칙 1). 좌표·거리=코드 계산 (원칙 2).

⚠ 면적(㎡)은 API 미제공(도서관=구 통합도서관·경로당=대한노인회 개별출처) → 목록·개수·거리만.
어린이집 정원은 시군구 기준(cpmsapi021) — 반경 개수와 단위 다름·참고. 지어내지 않음 (원칙 3·4).
"""

from __future__ import annotations

from typing import List, Optional

import httpx

from app.schemas.survey import FacilityCategory, SurveyFacility
from app.services import childcare, kakao, vworld
from app.services.geo import haversine_m

# 시설종류 → 카카오 키워드(복수 가능)
_KAKAO_KW = {
    "작은도서관": ["작은도서관", "도서관"],
    "경로당": ["경로당"],
    "어린이집": ["어린이집"],
}
_VWORLD_KINDS = {"경로당": ["경로당"]}


def _dedup_within(items: List[dict], radius: int) -> List[dict]:
    seen, out = set(), []
    for d in sorted(items, key=lambda x: x["dist_m"]):
        if d["dist_m"] > radius:
            continue
        key = (d["name"].replace(" ", ""), round(d["lat"], 4), round(d["lon"], 4))
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def _collect_kind(category: str, lat: float, lon: float, radius: int,
                  client: httpx.Client) -> List[dict]:
    raw: List[dict] = []
    for kw in _KAKAO_KW.get(category, []):
        for d in kakao.search_keyword(kw, lat, lon, radius, client=client):
            raw.append({"name": d["name"], "addr": d.get("addr", ""),
                        "lat": d["lat"], "lon": d["lon"],
                        "dist_m": round(haversine_m(lat, lon, d["lat"], d["lon"])),
                        "src": "kakao"})
    if category in _VWORLD_KINDS:
        vw, _ = vworld.search_vworld(lat, lon, radius, _VWORLD_KINDS[category], client=client)
        for d in vw:
            raw.append({"name": d["name"], "addr": "",
                        "lat": d["lat"], "lon": d["lon"],
                        "dist_m": round(haversine_m(lat, lon, d["lat"], d["lon"])),
                        "src": "vworld"})
    return _dedup_within(raw, radius)


def collect_survey_facilities(lat: float, lon: float, radius: int, sgg_code: str,
                              region_name: str = "",
                              client: Optional[httpx.Client] = None) -> List[FacilityCategory]:
    """반경 내 도서관·경로당·어린이집 현황. graceful — 실패 종류는 note 로."""
    own = client is None
    client = client or httpx.Client(timeout=20.0)
    try:
        cats: List[FacilityCategory] = []
        for category in ("작은도서관", "경로당", "어린이집"):
            try:
                rows = _collect_kind(category, lat, lon, radius, client)
            except Exception as e:
                cats.append(FacilityCategory(category=category, count=0,
                                             notes=[f"{category} 검색 실패 ({type(e).__name__})."]))
                continue
            items = [SurveyFacility(name=r["name"], addr=r["addr"],
                                    dist_m=r["dist_m"], src=r["src"]) for r in rows]
            notes = ["면적(㎡)은 개별 출처 미제공 — 목록·개수만 (사람 확인)."]
            cap = cap_scope = None
            if category == "어린이집":
                data, cnotes = childcare.fetch_childcare(sgg_code, region_name=region_name,
                                                         client=client)
                if data:
                    cap, cap_scope = data.get("total_capacity"), data.get("scope")
                    notes.append(f"정원 {cap}명은 {cap_scope} 시군구 기준(cpmsapi021) — 반경 개수와 단위 다름·참고.")
                else:
                    notes.extend(cnotes)
            cats.append(FacilityCategory(category=category, count=len(items), items=items,
                                         capacity=cap, capacity_scope=cap_scope, notes=notes))
        return cats
    finally:
        if own:
            client.close()
