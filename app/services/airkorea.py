"""에어코리아 대기질 — 한국환경공단 OpenAPI (DATA_GO_KR_API_KEY).

흐름: sigungu(시군구명) → getMsrstnList(측정소 검색) → stationName
      → getMsrstnAcctoRltmMesureDnsty(일평균 측정값) → facts[].
값 없음('-') 또는 API 오류는 빈 list + notes — graceful (절대 원칙 3).
캐시 키: airkorea:{sigungu}:{오늘날짜} → 하루 1회 호출.
"""

from __future__ import annotations

import os
from datetime import date
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key

_BASE = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc"

# 항목별 에어코리아 응답 필드 매핑
_ITEMS = [
    {"item": "PM2.5 (초미세먼지)", "field": "pm25Value", "unit": "㎍/㎥"},
    {"item": "PM10 (미세먼지)",    "field": "pm10Value",  "unit": "㎍/㎥"},
    {"item": "오존(O3)",           "field": "o3Value",    "unit": "ppm"},
    {"item": "이산화질소(NO2)",     "field": "no2Value",   "unit": "ppm"},
]

_ITEM_BY_NAME = {it["item"]: it for it in _ITEMS}


class AirkoreError(Exception):
    pass


def _api_key() -> str:
    k = os.getenv("DATA_GO_KR_API_KEY", "")
    if not k:
        raise AirkoreError("DATA_GO_KR_API_KEY 미설정")
    return k


def _check_result(body: dict, label: str) -> None:
    """에어코리아 응답 resultCode 확인. 오류면 AirkoreError."""
    code = body.get("response", {}).get("header", {}).get("resultCode", "")
    if code == "00":
        return
    msg = body.get("response", {}).get("header", {}).get("resultMsg", "")
    if code == "30":
        raise AirkoreError(f"API 키 미등록(code 30) — data.go.kr 에서 '에어코리아 대기오염정보' 활용신청 필요.")
    raise AirkoreError(f"에어코리아 API 오류 {code}: {msg}")


def _find_station(sigungu: str, sido: str, key: str, client: httpx.Client) -> Optional[str]:
    """시군구명 → 가장 가까운 측정소명. 없으면 sido로 재시도."""
    for addr in [sigungu, sido]:
        if not addr:
            continue
        r = client.get(
            f"{_BASE}/getMsrstnList",
            params={
                "addr": addr,
                "pageNo": 1,
                "numOfRows": 5,
                "returnType": "json",
                "serviceKey": key,
            },
            timeout=10.0,
        )
        r.raise_for_status()
        body = r.json()
        _check_result(body, "측정소 목록")
        items = body.get("response", {}).get("body", {}).get("items", []) or []
        if items:
            return items[0].get("stationName")
    return None


def _get_measurements(station: str, key: str, client: httpx.Client) -> Optional[dict]:
    """측정소명 → 일평균 측정값 dict. 데이터 없으면 None."""
    r = client.get(
        f"{_BASE}/getMsrstnAcctoRltmMesureDnsty",
        params={
            "stationName": station,
            "dataTerm": "DAILY",
            "pageNo": 1,
            "numOfRows": 1,
            "returnType": "json",
            "serviceKey": key,
            "ver": "1.0",
        },
        timeout=10.0,
    )
    r.raise_for_status()
    body = r.json()
    _check_result(body, "측정값")
    items = body.get("response", {}).get("body", {}).get("items", []) or []
    return items[0] if items else None


def fetch_air_quality(
    sido: str,
    sigungu: str,
    requested_items: Optional[List[str]] = None,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[List[dict], List[str]]:
    """에어코리아 측정값 → (facts[], notes[]).

    facts 형식: {item, value, national_avg, unit, source_tbl, year, source_type}
    requested_items: None이면 _ITEMS 전체. 지정하면 해당 항목만.
    """
    notes: List[str] = []

    try:
        key = _api_key()
    except AirkoreError as e:
        return [], [str(e)]

    cache_key = make_key("airkorea", sigungu, date.today().isoformat())
    if cache:
        cached = cache.get(cache_key)
        if cached:
            all_facts: List[dict] = cached.get("facts", [])
            cached_notes: List[str] = cached.get("notes", [])
            if requested_items is not None:
                all_facts = [f for f in all_facts if f["item"] in requested_items]
            return all_facts, cached_notes

    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        station = _find_station(sigungu, sido, key, client)
        if not station:
            note = f"에어코리아: '{sigungu}' 근처 측정소 미발견 — 건너뜀."
            return [], [note]

        meas = _get_measurements(station, key, client)
        if not meas:
            note = f"에어코리아: {station} 측정소 데이터 없음 — 건너뜀."
            return [], [note]

        today_year = date.today().year
        all_facts: List[dict] = []
        for cfg in _ITEMS:
            raw = meas.get(cfg["field"], "-")
            if raw in ("-", None, ""):
                continue
            try:
                value = float(raw)
            except (ValueError, TypeError):
                continue
            all_facts.append(
                {
                    "item": cfg["item"],
                    "value": value,
                    "national_avg": None,
                    "unit": cfg["unit"],
                    "source_tbl": f"에어코리아-{station}",
                    "year": today_year,
                    "source_type": "airkorea",
                }
            )

        if not all_facts:
            notes.append(f"에어코리아: {station} 측정소 전 항목 결측('-') — 건너뜀.")
        else:
            notes.append(f"에어코리아: {station} 측정소 기준 일평균 (실시간, {date.today().isoformat()}).")

        if cache and all_facts:
            cache.set(cache_key, {"facts": all_facts, "notes": notes})

        if requested_items is not None:
            all_facts = [f for f in all_facts if f["item"] in requested_items]
        return all_facts, notes

    except AirkoreError as e:
        return [], [str(e)]
    except Exception as e:
        err_str = str(e)
        if "SERVICE_KEY_IS_NOT_REGISTERED" in err_str or "code 30" in err_str:
            return [], ["에어코리아: API 키 미등록 — data.go.kr 에서 '에어코리아 대기오염정보' 활용신청 필요."]
        return [], [f"에어코리아 API 오류: {type(e).__name__}: {err_str[:120]}"]
    finally:
        if own:
            client.close()
