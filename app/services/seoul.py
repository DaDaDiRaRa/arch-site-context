"""서울 생활인구 — 서울 열린데이터광장 (SEOUL_API_KEY). 서울 전용.

행정동별 추계 생활인구(SPOP_LOCAL_RESD_DONG). 데이터는 ~5일 지연.
입력은 통계청 행정동코드(8자리, 서울 = 11로 시작). 주소→행정동코드 매핑은 별도(후속).
값 없음/오류는 graceful (절대 원칙 3). 캐시 키: seoul_pop:{dong}:{date}:{hour}.
검증된 엔드포인트만 사용 (docs/API_VERIFICATION_2026-06-26).
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key

_HOST = "http://openapi.seoul.go.kr:8088"
_SVC = "SPOP_LOCAL_RESD_DONG"


def _key() -> str:
    k = os.getenv("SEOUL_API_KEY", "")
    if not k:
        raise ValueError("SEOUL_API_KEY 미설정")
    return k


def _rows(j: dict) -> List[dict]:
    blk = j.get(_SVC, {})
    return blk.get("row", []) or [] if isinstance(blk, dict) else []


def _latest_date(key: str, client: httpx.Client) -> Optional[str]:
    """가장 최근 STDR_DE_ID (데이터는 최신순). 실패 시 None."""
    r = client.get(f"{_HOST}/{key}/json/{_SVC}/1/1/", timeout=15.0)
    r.raise_for_status()
    rows = _rows(r.json())
    return rows[0].get("STDR_DE_ID") if rows else None


def fetch_living_population(
    adstrd_code: str,
    hour: str = "15",
    date_id: Optional[str] = None,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """행정동 생활인구 — 최신 가용일의 대표 시간대(기본 15시) 총 생활인구.

    Returns:
        ({value, date, hour, dong_code}, notes) 또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    if not adstrd_code or not str(adstrd_code).startswith("11"):
        return None, [f"생활인구: 서울 행정동코드(11…)만 지원 — '{adstrd_code}' 건너뜀."]

    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        ymd = date_id or _latest_date(key, client)
        if not ymd:
            return None, ["생활인구: 최신 가용일 확인 실패 — 건너뜀."]

        cache_key = make_key("seoul_pop", adstrd_code, ymd, hour)
        if cache:
            cached = cache.get(cache_key)
            if cached:
                return cached.get("data"), cached.get("notes", [])

        url = f"{_HOST}/{key}/json/{_SVC}/1/5/{ymd}/{hour}/{adstrd_code}"
        r = client.get(url, timeout=15.0)
        r.raise_for_status()
        rows = _rows(r.json())
        if not rows:
            return None, [f"생활인구: {adstrd_code} {ymd} {hour}시 데이터 없음."]

        try:
            value = round(float(rows[0]["TOT_LVPOP_CO"]))
        except (KeyError, TypeError, ValueError):
            return None, ["생활인구: 값 파싱 실패."]

        data = {"value": value, "date": ymd, "hour": hour, "dong_code": adstrd_code}
        notes.append(f"생활인구: 행정동 {adstrd_code} {ymd} {hour}시 추계 {value:,}명 (서울 열린데이터 — 참고).")
        if cache:
            cache.set(cache_key, {"data": data, "notes": notes})
        return data, notes

    except ValueError as e:
        return None, [str(e)]
    except Exception as e:
        return None, [f"생활인구 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()
