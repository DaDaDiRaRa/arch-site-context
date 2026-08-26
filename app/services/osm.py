"""OSM Overpass API — 카카오 누락 시설 보완 (공공시설 위주).

무료 API, 키 불필요. 카카오 결과와 dedup 후 병합 (facilities.py 에서 처리).
공공시설(경로당·도서관·학교·병원 등)은 OSM 커버리지가 카카오보다 양호.
상업시설(식당·카페 등)은 카카오 우선 — OSM 매핑 없으면 생략.
오류 시 빈 리스트 반환 (graceful — 절대 원칙 3).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import httpx

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

#: Overpass 는 **보완 소스**다(주 데이터원 아님) — 못 닿으면 빨리 포기해야 한다.
#: 실측(2026-08-26): Overpass 미도달 시 호출당 40.7s(연결 타임아웃 20s × IPv6→IPv4 재시도),
#: 번들 경로의 9회 호출이 **366초**를 태우면서 결과는 0건이었다. 관측된 /ask 번들 365.4s 와 일치.
#: → 연결은 3초만 기다린다. read 는 그대로 20s(도달할 때의 동작은 안 바꾼다).
_TIMEOUT = httpx.Timeout(connect=3.0, read=20.0, write=10.0, pool=5.0)

# 한국어 시설명 → OSM 태그 목록. 복수 태그셋은 union.
KIND_TO_OSM: Dict[str, List[Dict[str, str]]] = {
    "경로당":    [{"amenity": "social_facility"}],
    "마을회관":  [{"amenity": "community_centre"}],
    "도서관":    [{"amenity": "library"}],
    "학교":      [{"amenity": "school"}],
    "초등학교":  [{"amenity": "school"}],
    "중학교":    [{"amenity": "school"}],
    "고등학교":  [{"amenity": "school"}],
    "어린이집":  [{"amenity": "kindergarten"}],
    "유치원":    [{"amenity": "kindergarten"}],
    "병원":      [{"amenity": "hospital"}],
    "의원":      [{"amenity": "clinic"}],
    "약국":      [{"amenity": "pharmacy"}],
    "공원":      [{"leisure": "park"}],
    "어린이공원":[{"leisure": "playground"}],
    "주차장":    [{"amenity": "parking"}],
    "버스정류장":[{"highway": "bus_stop"}],
    "소방서":    [{"amenity": "fire_station"}],
    "경찰서":    [{"amenity": "police"}],
    "주민센터":  [{"amenity": "townhall"}],
}


def _build_query(tags: Dict[str, str], lat: float, lon: float, radius_m: int) -> str:
    """태그셋 + 좌표 → Overpass QL 쿼리."""
    flt = "".join(f'["{k}"="{v}"]' for k, v in tags.items())
    return (
        f"[out:json][timeout:20];\n"
        f"(node{flt}(around:{radius_m},{lat},{lon});\n"
        f" way{flt}(around:{radius_m},{lat},{lon}););\n"
        f"out center;"
    )


def _parse_elements(elements: list, kind: str) -> List[dict]:
    """Overpass 응답 elements → [{name, lat, lon, kind}]."""
    results = []
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name", "")
        if not name:
            continue
        if el["type"] == "node":
            elat, elon = el.get("lat"), el.get("lon")
        elif "center" in el:
            elat, elon = el["center"]["lat"], el["center"]["lon"]
        else:
            continue
        if elat is None or elon is None:
            continue
        results.append({"name": name, "lat": float(elat), "lon": float(elon), "kind": kind})
    return results


def search_osm(
    lat: float,
    lon: float,
    radius_m: int,
    kinds: List[str],
    client: Optional[httpx.Client] = None,
) -> Tuple[List[dict], List[str]]:
    """OSM Overpass 로 시설 검색 → ([{name, lat, lon, kind}], notes).

    OSM 매핑 없는 kind는 조용히 생략 (카카오가 더 정확).
    오류 시 빈 리스트 — 호출자가 카카오 결과만 씀.

    ★ **서킷 브레이커**: 첫 호출이 실패하면 남은 kind 를 건너뛴다. Overpass 가 안 닿을 때
    kind 마다 타임아웃을 다 기다리면 **결과 0건에 366초**를 태운다(실측 — §_TIMEOUT 주석).
    한 번 못 닿으면 그 요청 안에서는 계속 못 닿는다고 보는 게 맞다. 건너뛴 사실은 notes 로
    올려 호출자가 표기한다 — 조용히 삼키지 않는다(절대 원칙 3).
    """
    results: List[dict] = []
    notes: List[str] = []
    own = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)

    planned = [(k, tags) for k in kinds for tags in (KIND_TO_OSM.get(k) or [])]
    done = 0
    try:
        for kind, tags in planned:
            query = _build_query(tags, lat, lon, radius_m)
            try:
                r = client.post(_OVERPASS_URL, data={"data": query}, timeout=_TIMEOUT)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                elements = r.json().get("elements", [])
                results.extend(_parse_elements(elements, kind))
                done += 1
            except Exception as e:  # noqa: BLE001 — 보완 소스, 실패해도 카카오로 진행
                skipped = len(planned) - done - 1
                notes.append(
                    f"OSM Overpass 미응답({type(e).__name__}) — 남은 {skipped}건 조회를 건너뜁니다"
                    " (보완 소스, 카카오·VWorld 결과로 진행)."
                    if skipped > 0 else
                    f"OSM Overpass 미응답({type(e).__name__}) — 카카오·VWorld 결과로 진행."
                )
                break  # 서킷 브레이커 — 남은 kind 는 시도하지 않는다
    finally:
        if own:
            client.close()

    return results, notes
