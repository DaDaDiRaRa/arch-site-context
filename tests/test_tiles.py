"""타일 수학 단위테스트 (네트워크 불필요)."""

from __future__ import annotations

import math

from app.services.tiles import (
    TILE_SIZE,
    ground_resolution,
    latlon_to_global_px,
    meters_to_pixels,
    zoom_for_radius,
)


def test_ground_resolution_equator_z0() -> None:
    # 적도 z0 ≈ 156543 m/px
    assert math.isclose(ground_resolution(0.0, 0), 156543.0339, rel_tol=1e-4)


def test_ground_resolution_halves_per_zoom() -> None:
    a = ground_resolution(37.5, 14)
    b = ground_resolution(37.5, 15)
    assert math.isclose(a / b, 2.0, rel_tol=1e-9)


def test_latitude_shrinks_resolution() -> None:
    # 위도가 높을수록 m/px 작아진다 (cos 보정)
    assert ground_resolution(60.0, 14) < ground_resolution(0.0, 14)


def test_global_px_center_of_world() -> None:
    # lon=0,lat=0 → 월드 정중앙
    world = TILE_SIZE * (2 ** 10)
    x, y = latlon_to_global_px(0.0, 0.0, 10)
    assert math.isclose(x, world / 2, rel_tol=1e-9)
    assert math.isclose(y, world / 2, rel_tol=1e-6)


def test_meters_to_pixels_roundtrip() -> None:
    # 1px 만큼의 거리는 다시 1px
    lat, z = 37.5, 16
    m = ground_resolution(lat, z)  # 1px에 해당하는 m
    assert math.isclose(meters_to_pixels(m, lat, z), 1.0, rel_tol=1e-9)


def test_zoom_for_radius_fits() -> None:
    lat, radius, target = 37.5, 2000, 320
    z = zoom_for_radius(lat, radius, target)
    # 선택된 줌에서 반경 픽셀이 target 이내
    assert meters_to_pixels(radius, lat, z) <= target
    # 한 단계 더 확대하면 초과 (가장 큰 줌을 골랐다) — 클램프 경계 제외
    if z < 18:
        assert meters_to_pixels(radius, lat, z + 1) > target
