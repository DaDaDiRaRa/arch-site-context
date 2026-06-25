"""모드 B 오케스트레이션 — 주소→좌표→반경검색→거리→밴드→중복제거→집계.

facts는 코드가 만든다 (절대 원칙 2). 좌표·거리·집계 전부 코드 계산, WGS84.
0건도 정상 (빈 배열 + 0). 데이터로 답 못하면 멈추지만, '결과 없음'은 유효한 답.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

import httpx

from app.schemas.facility import Center, Facility, FacilityResult
from app.services import kakao
from app.services.geo import bbox, haversine_m, radius_band
from app.services.resolve import resolve_address


def _dedup_key(name: str, lat: float, lon: float) -> tuple:
    """이름 + 좌표(소수 6자리, ~0.1m) 기준 중복 키."""
    return (name.strip(), round(lat, 6), round(lon, 6))


def build_facility_result(
    address: str,
    kinds: List[str],
    radii: List[int],
    client: Optional[httpx.Client] = None,
    loc=None,
) -> FacilityResult:
    """입력을 받아 FacilityResult를 구성한다.

    loc: 이미 해석된 주소(ResolvedAddress)가 있으면 재해석 생략 (P9 비교 — 후보지당 1회).
    """
    own = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        loc = loc or resolve_address(address, client=client)
        clat, clon = loc.lat, loc.lon

        radii_sorted = sorted(set(int(r) for r in radii))
        max_radius = radii_sorted[-1] if radii_sorted else 2000

        # 최대 반경을 감싸는 사각형 → 적응 분할 검색 (45건 상한 회피, P1.5)
        bbox_rect = bbox(clat, clon, max_radius)

        seen: set = set()
        results: List[Facility] = []
        notes: List[str] = list(loc.notes)

        for kind in kinds:
            res = kakao.search_keyword_complete(kind, bbox_rect, client=client)
            for d in res["docs"]:
                key = _dedup_key(d["name"], d["lat"], d["lon"])
                if key in seen:
                    continue
                dist = haversine_m(clat, clon, d["lat"], d["lon"])
                band = radius_band(dist, radii_sorted)
                if band is None:
                    # 사각형 모서리 등 최대 반경 밖 → 제외 (원형 반경으로 정확히 자름)
                    continue
                seen.add(key)
                results.append(
                    Facility(
                        kind=kind,
                        name=d["name"],
                        lat=d["lat"],
                        lon=d["lon"],
                        dist_m=round(dist),
                        radius_band=band,
                    )
                )
            if res["capped"]:
                notes.append(
                    f"'{kind}': 일부 영역이 카카오 검색 상한에 도달해 누락 가능 (참고)."
                )

        results.sort(key=lambda f: f.dist_m)

        # counts: 누적 — 반경 R 이내(dist<=R) 시설을 kind별로 센다.
        counts: Dict[str, Dict[str, int]] = {}
        for r in radii_sorted:
            per_kind: Dict[str, int] = {k: 0 for k in kinds}
            for f in results:
                if f.dist_m <= r:
                    per_kind[f.kind] = per_kind.get(f.kind, 0) + 1
            counts[str(r)] = per_kind

        return FacilityResult(
            center=Center(lat=clat, lon=clon, address=loc.address),
            results=results,
            counts=counts,
            source="kakao",
            base_date=date.today().isoformat(),
            notes=notes,
        )
    finally:
        if own:
            client.close()
