"""하버사인·반경밴드 단위테스트 (네트워크 불필요)."""

from __future__ import annotations

import math

from app.services.geo import (
    EARTH_RADIUS_M,
    bbox,
    haversine_m,
    radius_band,
    split_rect,
)

# 위도 1도 = 적도/자오선에서 R*pi/180
ONE_DEG_M = EARTH_RADIUS_M * math.pi / 180  # ≈ 111195 m


def test_same_point_is_zero() -> None:
    assert haversine_m(37.5, 127.0, 37.5, 127.0) == 0.0


def test_one_degree_latitude() -> None:
    # 경도 고정, 위도 1도 차이 → ONE_DEG_M (오차 0.01%)
    d = haversine_m(0.0, 0.0, 1.0, 0.0)
    assert math.isclose(d, ONE_DEG_M, rel_tol=1e-4)


def test_one_degree_longitude_at_equator() -> None:
    # 적도에서 경도 1도 차이 → ONE_DEG_M
    d = haversine_m(0.0, 0.0, 0.0, 1.0)
    assert math.isclose(d, ONE_DEG_M, rel_tol=1e-4)


def test_symmetry() -> None:
    a = haversine_m(37.5219, 126.9245, 37.5260, 126.9265)
    b = haversine_m(37.5260, 126.9265, 37.5219, 126.9245)
    assert math.isclose(a, b, rel_tol=1e-12)


def test_known_short_distance() -> None:
    # 약 100m 남북: 위도 0.0009도 ≈ 100.1m
    d = haversine_m(37.5000, 127.0000, 37.5009, 127.0000)
    assert 95 <= d <= 105


def test_radius_band_assigns_smallest() -> None:
    radii = [500, 1000, 2000]
    assert radius_band(420, radii) == "500"
    assert radius_band(500, radii) == "500"  # 경계 포함
    assert radius_band(501, radii) == "1000"
    assert radius_band(1500, radii) == "2000"
    assert radius_band(2001, radii) is None  # 모든 밴드 밖


def test_radius_band_unsorted_input() -> None:
    # 입력이 정렬 안 돼 있어도 가장 작은 밴드를 고른다
    assert radius_band(700, [2000, 500, 1000]) == "1000"


def test_bbox_contains_circle_edge() -> None:
    # bbox는 반경 원을 외접 → 동/서/남/북 끝점이 사각형 안에 들어온다
    lat, lon, r = 37.5, 127.0, 1000
    min_lon, min_lat, max_lon, max_lat = bbox(lat, lon, r)
    assert min_lat < lat < max_lat
    assert min_lon < lon < max_lon
    # 정북 1000m 지점 위도가 bbox 위쪽 경계 이내
    north_lat = lat + 1000 / 111320.0
    assert north_lat <= max_lat + 1e-9


def test_split_rect_partitions() -> None:
    rect = (126.0, 37.0, 127.0, 38.0)
    quads = split_rect(rect)
    assert len(quads) == 4
    # 4분할 넓이 합 == 원본 넓이 (중복·누락 없음)
    def area(r):
        return (r[2] - r[0]) * (r[3] - r[1])
    assert math.isclose(sum(area(q) for q in quads), area(rect), rel_tol=1e-12)
    # 모든 쿼드가 원본 안에 포함
    for q in quads:
        assert q[0] >= rect[0] and q[1] >= rect[1]
        assert q[2] <= rect[2] and q[3] <= rect[3]
