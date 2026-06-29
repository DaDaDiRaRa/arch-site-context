"""기상청 단기예보 — KMA apihub (KMA_KEY, authKey 방식).

좌표(WGS84) → 기상청 격자(LCC, dfs_xy) → 단기예보 → 기온(TMP) 등.
apihub 는 응답이 느려 timeout 넉넉히. 값 없음/오류는 graceful (절대 원칙 3).
캐시 키: kma:{nx}:{ny}:{base_date}:{base_time}.
검증된 엔드포인트만 사용 (docs/API_VERIFICATION_2026-06-26).
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key

_URL = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst"
# 단기예보 발표시각 (KST)
_BASE_TIMES = ["2300", "2000", "1700", "1400", "1100", "0800", "0500", "0200"]


def _key() -> str:
    k = os.getenv("KMA_KEY", "")
    if not k:
        raise ValueError("KMA_KEY 미설정")
    return k


def dfs_xy(lat: float, lon: float) -> Tuple[int, int]:
    """WGS84 위경도 → 기상청 단기예보 격자 (nx, ny). 기상청 공식 LCC 변환."""
    RE, GRID = 6371.00877, 5.0
    SLAT1, SLAT2, OLON, OLAT, XO, YO = 30.0, 60.0, 126.0, 38.0, 43, 136
    D = math.pi / 180.0
    re = RE / GRID
    s1, s2, ol, oa = SLAT1 * D, SLAT2 * D, OLON * D, OLAT * D
    sn = math.tan(math.pi * 0.25 + s2 * 0.5) / math.tan(math.pi * 0.25 + s1 * 0.5)
    sn = math.log(math.cos(s1) / math.cos(s2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + s1 * 0.5)
    sf = (sf ** sn) * math.cos(s1) / sn
    ro = math.tan(math.pi * 0.25 + oa * 0.5)
    ro = re * sf / (ro ** sn)
    ra = math.tan(math.pi * 0.25 + lat * D * 0.5)
    ra = re * sf / (ra ** sn)
    theta = lon * D - ol
    if theta > math.pi:
        theta -= 2 * math.pi
    if theta < -math.pi:
        theta += 2 * math.pi
    theta *= sn
    nx = int(ra * math.sin(theta) + XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + YO + 0.5)
    return nx, ny


def _latest_base(now: datetime) -> Tuple[str, str]:
    """현재시각 기준 가장 최근 발표 base_date, base_time (발표 후 ~10분 여유)."""
    cand = now - timedelta(minutes=10)
    hm = cand.strftime("%H%M")
    for bt in _BASE_TIMES:
        if hm >= bt:
            return cand.strftime("%Y%m%d"), bt
    # 02시 이전 → 전날 2300
    return (cand - timedelta(days=1)).strftime("%Y%m%d"), "2300"


def fetch_weather(
    lat: float,
    lon: float,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
    now: Optional[datetime] = None,
) -> Tuple[Optional[dict], List[str]]:
    """좌표 기준 단기예보 — 가장 이른 예보시점의 기온·강수확률·하늘상태.

    Returns:
        ({temp_c, pop_pct, sky, fcst_date, fcst_time, nx, ny}, notes) 또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    nx, ny = dfs_xy(lat, lon)
    base_date, base_time = _latest_base(now or datetime.now())
    cache_key = make_key("kma", str(nx), str(ny), base_date, base_time)
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return cached.get("data"), cached.get("notes", [])

    own = client is None
    client = client or httpx.Client(timeout=35.0)
    try:
        r = client.get(
            _URL,
            params={
                "pageNo": 1, "numOfRows": 300, "dataType": "JSON",
                "base_date": base_date, "base_time": base_time,
                "nx": nx, "ny": ny, "authKey": key,
            },
            timeout=35.0,
        )
        r.raise_for_status()
        body = r.json().get("response", {})
        code = body.get("header", {}).get("resultCode")
        if code != "00":
            msg = body.get("header", {}).get("resultMsg", "")
            return None, [f"기상청: 예보 없음/오류 ({code} {msg})."]

        items = body.get("body", {}).get("items", {}).get("item", []) or []
        if not items:
            return None, ["기상청: 예보 데이터 없음."]

        # 가장 이른 예보시점(fcstDate+fcstTime) 선택
        first = min(items, key=lambda it: (it["fcstDate"], it["fcstTime"]))
        fd, ft = first["fcstDate"], first["fcstTime"]
        by_cat = {it["category"]: it["fcstValue"]
                  for it in items if it["fcstDate"] == fd and it["fcstTime"] == ft}

        def _num(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        sky_map = {"1": "맑음", "3": "구름많음", "4": "흐림"}
        data = {
            "temp_c": _num(by_cat.get("TMP")),
            "pop_pct": _num(by_cat.get("POP")),
            "sky": sky_map.get(by_cat.get("SKY", ""), None),
            "fcst_date": fd,
            "fcst_time": ft,
            "nx": nx,
            "ny": ny,
        }
        notes.append(f"기상청 단기예보: 격자({nx},{ny}) {fd} {ft} 기준 (발표 {base_date} {base_time}).")
        if cache:
            cache.set(cache_key, {"data": data, "notes": notes})
        return data, notes

    except ValueError as e:
        return None, [str(e)]
    except Exception as e:
        return None, [f"기상청 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()
