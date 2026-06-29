"""TMAP 보행자 경로 기반 등시선(isochrone) 계산.

TMAP pedestrian route API를 n_directions 방향으로 쏘아
각 방향에서 time_s 초 걷는 지점을 찾은 뒤 폴리곤으로 연결한다.
원(직선반경)이 아니라 실제 도로망 기반 도달권 → 강·고속도로를 넘지 않는다.

호출 수: len(time_limits_min) × n_directions (기본 3×16 = 48).
ThreadPoolExecutor로 병렬 호출 → 실제 소요 ~3-5초.
실패(네트워크·경로 없음)는 해당 꼭짓점 생략 — graceful.
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import httpx

_TMAP_KEY = os.getenv("TMAP_KEY", "")
_TMAP_BASE = "https://apis.openapi.sk.com/tmap"
_WALK_SPEED_MPS = 1.1  # ~4 km/h 보행 속도 m/s


def _offset_latlon(lat: float, lon: float, bearing_deg: float, dist_m: float) -> tuple[float, float]:
    """(lat, lon)에서 bearing_deg 방향으로 dist_m 이동한 좌표 (WGS84)."""
    R = 6_371_000.0
    d = dist_m / R
    b = math.radians(bearing_deg)
    lat1, lon1 = math.radians(lat), math.radians(lon)
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(b))
    lon2 = lon1 + math.atan2(
        math.sin(b) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)


def _call_route(
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    client: httpx.Client,
) -> Optional[dict]:
    """TMAP 보행자 경로 호출. 실패 시 None."""
    try:
        r = client.post(
            f"{_TMAP_BASE}/routes/pedestrian",
            headers={"appKey": _TMAP_KEY, "Content-Type": "application/json"},
            json={
                "startX": str(round(start_lon, 6)),
                "startY": str(round(start_lat, 6)),
                "endX": str(round(end_lon, 6)),
                "endY": str(round(end_lat, 6)),
                "startName": "S",
                "endName": "E",
                "reqCoordType": "WGS84GEO",
                "resCoordType": "WGS84GEO",
                "speed": 67,
            },
            timeout=8,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _trim_route_at_time(geojson: dict, target_s: float) -> Optional[tuple[float, float]]:
    """경로 GeoJSON을 target_s 초 지점에서 자른 좌표 (lat, lon) 반환.

    TMAP feature 구조:
    - LineString feature: geometry.coordinates = [[lon, lat], ...]
      properties.time = 이 구간 소요시간(초)
    - 구간 시간 합산이 target_s 를 넘는 순간 해당 구간 내 보간.
    """
    elapsed = 0.0

    for feat in geojson.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") != "LineString":
            continue
        coords = geom.get("coordinates", [])  # [[lon, lat], ...]
        seg_time = float(feat.get("properties", {}).get("time", 0))
        if not coords or seg_time <= 0:
            continue

        if elapsed + seg_time >= target_s:
            frac = (target_s - elapsed) / seg_time
            # 구간 내 서브-세그먼트 길이 합
            seg_lens = [
                math.hypot(coords[i + 1][0] - coords[i][0], coords[i + 1][1] - coords[i][1])
                for i in range(len(coords) - 1)
            ]
            total_len = sum(seg_lens) or 1e-9
            target_len = frac * total_len
            accum = 0.0
            for i, slen in enumerate(seg_lens):
                if accum + slen >= target_len:
                    sub = (target_len - accum) / slen if slen > 0 else 0
                    lon = coords[i][0] + (coords[i + 1][0] - coords[i][0]) * sub
                    lat = coords[i][1] + (coords[i + 1][1] - coords[i][1]) * sub
                    return lat, lon
                accum += slen
            last = coords[-1]
            return last[1], last[0]

        elapsed += seg_time

    # 경로가 target_s 보다 짧음 → 마지막 좌표 반환
    for feat in reversed(geojson.get("features", [])):
        if feat.get("geometry", {}).get("type") == "LineString":
            c = feat["geometry"]["coordinates"]
            if c:
                return c[-1][1], c[-1][0]
    return None


def compute_isochrone(
    lat: float,
    lon: float,
    time_limits_min: Optional[list[int]] = None,
    n_directions: int = 16,
    client: Optional[httpx.Client] = None,
) -> dict[int, list[tuple[float, float]]]:
    """TMAP 보행자 경로 기반 등시선 폴리곤 계산.

    Args:
        lat, lon: 중심 좌표
        time_limits_min: 등시선 시간(분) 목록, 기본 [5, 10, 15]
        n_directions: 방사 방향 수 (많을수록 정밀, API 호출 비례)
        client: httpx.Client (없으면 새로 생성)

    Returns:
        {time_min: [(lat, lon), ...]} — 시간별 폴리곤 꼭짓점 리스트.
        빈 리스트 = 해당 시간 전방향 실패.
    """
    if not _TMAP_KEY:
        return {}
    if time_limits_min is None:
        time_limits_min = [5, 10, 15]

    own = client is None
    if own:
        client = httpx.Client(timeout=10.0)

    try:
        bearings = [360.0 * i / n_directions for i in range(n_directions)]

        # 작업 목록: (t_min, bearing_idx, t_s, target_lat, target_lon)
        tasks: list[tuple] = []
        for t_min in time_limits_min:
            t_s = float(t_min * 60)
            overshoot_m = _WALK_SPEED_MPS * t_s * 2.5  # 실제 도로는 직선보다 ~25-50% 더 걸림
            for i_b, b in enumerate(bearings):
                tlat, tlon = _offset_latlon(lat, lon, b, overshoot_m)
                tasks.append((t_min, i_b, t_s, tlat, tlon))

        results: dict[int, list] = {t: [None] * n_directions for t in time_limits_min}

        def _worker(task):
            t_min, b_idx, t_s, tlat, tlon = task
            geo = _call_route(lat, lon, tlat, tlon, client)
            if geo is None:
                return t_min, b_idx, None
            return t_min, b_idx, _trim_route_at_time(geo, t_s)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = {pool.submit(_worker, t): t for t in tasks}
            for f in as_completed(futs):
                try:
                    t_min, b_idx, pt = f.result()
                    results[t_min][b_idx] = pt
                except Exception:
                    pass

        return {
            t_min: [pt for pt in pts if pt is not None]
            for t_min, pts in results.items()
        }
    finally:
        if own:
            client.close()
