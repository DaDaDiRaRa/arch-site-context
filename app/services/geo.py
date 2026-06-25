"""거리·반경 계산 — 코드만 할 수 있는 계산 (절대 원칙 2).

좌표는 전부 WGS84. 하버사인으로 두 점 사이 거리(m)를 구한다.
"""

from __future__ import annotations

import math
from typing import List, Optional

# 평균 지구 반지름 (m, WGS84 권장값)
EARTH_RADIUS_M = 6_371_008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 WGS84 좌표 사이의 대권 거리(m)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


# 위도 1도당 미터 (구면 근사). 경도는 위도에 따라 cos 보정.
M_PER_DEG_LAT = 111_320.0


def bbox(lat: float, lon: float, radius_m: float) -> tuple:
    """중심+반경을 감싸는 사각형 (minLon, minLat, maxLon, maxLat), WGS84.

    원을 외접하는 정사각형이라 모서리는 반경을 넘는다 → 거리필터로 잘라낸다.
    카카오 키워드검색 rect 파라미터 형식("좌,하,우,상")과 동일 순서.
    """
    dlat = radius_m / M_PER_DEG_LAT
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    dlon = radius_m / (M_PER_DEG_LAT * cos_lat)
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def split_rect(rect: tuple) -> List[tuple]:
    """사각형을 4분할 (quadrant). 중복 없는 분할."""
    min_lon, min_lat, max_lon, max_lat = rect
    mid_lon = (min_lon + max_lon) / 2
    mid_lat = (min_lat + max_lat) / 2
    return [
        (min_lon, min_lat, mid_lon, mid_lat),
        (mid_lon, min_lat, max_lon, mid_lat),
        (min_lon, mid_lat, mid_lon, max_lat),
        (mid_lon, mid_lat, max_lon, max_lat),
    ]


def radius_band(dist_m: float, radii: List[int]) -> Optional[str]:
    """거리가 속하는 '가장 작은' 반경 밴드 문자열을 반환.

    radii는 오름차순 가정. 모든 밴드 밖이면 None (집계·목록에서 제외).
    예: dist=420, radii=[500,1000,2000] -> "500".
    """
    for r in sorted(radii):
        if dist_m <= r:
            return str(r)
    return None
