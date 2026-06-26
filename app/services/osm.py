"""OSM Overpass API — 카카오 누락 시설 보완 (공공시설 위주).

무료 API, 키 불필요. 카카오 결과와 dedup 후 병합 (facilities.py 에서 처리).
공공시설(경로당·도서관·학교·병원 등)은 OSM 커버리지가 카카오보다 양호.
상업시설(식당·카페 등)은 카카오 우선 — OSM 매핑 없으면 생략.
오류 시 빈 리스트 반환 (graceful — 절대 원칙 3).
"""

from __future__ import annotations

from typing import Dict, List, Optional

import httpx

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

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
) -> List[dict]:
    """OSM Overpass 로 시설 검색. 결과: [{name, lat, lon, kind}].

    OSM 매핑 없는 kind는 조용히 생략 (카카오가 더 정확).
    오류 시 빈 리스트 — 호출자가 카카오 결과만 씀.
    """
    results: List[dict] = []
    own = client is None
    client = client or httpx.Client(timeout=25.0)

    try:
        for kind in kinds:
            tag_sets = KIND_TO_OSM.get(kind)
            if not tag_sets:
                continue
            for tags in tag_sets:
                query = _build_query(tags, lat, lon, radius_m)
                try:
                    r = client.post(_OVERPASS_URL, data={"data": query}, timeout=20.0)
                    if r.status_code != 200:
                        continue
                    elements = r.json().get("elements", [])
                    results.extend(_parse_elements(elements, kind))
                except Exception:
                    continue
    except Exception:
        pass
    finally:
        if own:
            client.close()

    return results
