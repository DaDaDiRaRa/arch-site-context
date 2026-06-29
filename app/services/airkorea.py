"""에어코리아 대기질 — 한국환경공단 OpenAPI (DATA_GO_KR_API_KEY).

흐름: sido → getCtprvnRltmMesureDnsty(시도 전체 측정소+측정값) → 시군구명으로 측정소 선택 → facts[].
  ※ 측정소 검색 서비스(MsrstnInfoInqireSvc/getMsrstnList)는 별도 활용신청이라 미승인(403)이 잦아
    의존하지 않는다. 측정값 서비스(ArpltnInforInqireSvc)만으로 시도 목록을 받아 이름 매칭한다.
값 없음('-') 또는 API 오류는 빈 list + notes — graceful (절대 원칙 3).
캐시 키: airkorea:{sigungu}:{오늘날짜} → 하루 1회 호출.
"""

from __future__ import annotations

import os
from datetime import date
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key
from app.services.http_retry import request_with_retry

_BASE = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc"

# getCtprvnRltmMesureDnsty sidoName 은 축약형(서울/경기/충북…) 요구 → 정식 시도명 매핑
_SIDO_SHORT = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원도": "강원", "강원특별자치도": "강원",
    "충청북도": "충북", "충청남도": "충남",
    "전라북도": "전북", "전북특별자치도": "전북", "전라남도": "전남",
    "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주",
}


def _sido_short(sido: str) -> str:
    if not sido:
        return ""
    return _SIDO_SHORT.get(sido, sido[:2])

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


def _fetch_sido_stations(sido: str, key: str, client: httpx.Client) -> List[dict]:
    """시도 전체 측정소 실시간 측정값 목록 (측정값 동봉)."""
    r = request_with_retry(
        client,
        "GET",
        f"{_BASE}/getCtprvnRltmMesureDnsty",
        params={
            "sidoName": _sido_short(sido) or "서울",
            "returnType": "json",
            "numOfRows": 100,
            "pageNo": 1,
            "ver": "1.0",
            "serviceKey": key,
        },
        timeout=10.0,
    )
    r.raise_for_status()
    body = r.json()
    _check_result(body, "시도 측정값")
    return body.get("response", {}).get("body", {}).get("items", []) or []


def _pick_station(items: List[dict], sigungu: str) -> Optional[dict]:
    """시도 측정소 목록에서 시군구명에 해당하는 측정소 선택.

    이름 매칭만 — 매칭 없으면 None(건너뜀). 임의 측정소로 대체하지 않는다 (절대 원칙 3).
    ※ 좌표 기반 최근접은 측정소검색(MsrstnInfoInqireSvc) 승인 후 개선 가능 (현재 403).
    """
    if not items or not sigungu:
        return None
    for it in items:
        if it.get("stationName") == sigungu:
            return it
    # 부분일치 폴백: 1글자 어간(중구→'중', 서구→'서')은 무관 측정소 오매칭 위험 → 2글자 이상만.
    short = sigungu.rstrip("구시군")  # '영등포구'→'영등포'
    if len(short) >= 2:
        for it in items:
            if short in (it.get("stationName") or ""):
                return it
    return None


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
        items = _fetch_sido_stations(sido, key, client)
        meas = _pick_station(items, sigungu)
        if not meas:
            note = f"에어코리아: '{sigungu}' 일치 측정소 없음 — 건너뜀 (좌표기반 최근접은 측정소검색 승인 후)."
            return [], [note]
        station = meas.get("stationName") or "?"

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
            notes.append(f"에어코리아: {station} 측정소 기준 실시간 측정값 ({date.today().isoformat()}).")

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
