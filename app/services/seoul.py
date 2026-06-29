"""서울 생활인구 — 서울 열린데이터광장 (SEOUL_API_KEY). 서울 전용.

행정동별 추계 생활인구(SPOP_LOCAL_RESD_DONG). 데이터는 ~5일 지연.
입력은 통계청 행정동코드(8자리, 서울 = 11로 시작). 주소→행정동코드 매핑은 별도(후속).
값 없음/오류는 graceful (절대 원칙 3). 캐시 키: seoul_pop:{dong}:{date}:{hour}.
검증된 엔드포인트만 사용 (docs/API_VERIFICATION_2026-06-26).
"""

from __future__ import annotations

import os
from datetime import date
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key
from app.services.http_retry import request_with_retry

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


def _latest_date(
    key: str, client: httpx.Client, cache: Optional[Cache] = None
) -> Optional[str]:
    """가장 최근 STDR_DE_ID (데이터는 최신순). 실패 시 None.

    이 1건 조회가 서울 서버에서 ~3초 걸리는데(전체 정렬), 결과(최신 가용일)는 하루 1회만
    바뀌고 행정동과 무관 → 오늘 날짜로 캐시. 같은 날 두 번째 호출부터 0콜 (warm 즉시).
    데이터는 ~5일 지연이라 하루 단위 캐시 무효화로 충분 (절대 원칙 4 — 참고값).
    """
    ck = make_key("seoul_latest", date.today().isoformat())
    if cache:
        c = cache.get(ck)
        if c and c.get("date"):
            return c["date"]
    r = request_with_retry(client, "GET", f"{_HOST}/{key}/json/{_SVC}/1/1/", timeout=15.0)
    r.raise_for_status()
    rows = _rows(r.json())
    ymd = rows[0].get("STDR_DE_ID") if rows else None
    if cache and ymd:
        cache.set(ck, {"date": ymd})
    return ymd


def fetch_living_population(
    adstrd_code: Optional[str] = None,
    hour: str = "15",
    date_id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """행정동 생활인구 — 최신 가용일의 대표 시간대(기본 15시) 총 생활인구.

    adstrd_code 미지정 시 lat/lon 으로 자동 해석 (카카오 행정동코드 H[:8]).
    Returns:
        ({value, date, hour, dong_code}, notes) 또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        # 좌표 → 행정동코드 자동 해석 (서울 ADSTRD_CODE_SE = 카카오 행정동 H코드[:8])
        if not adstrd_code and lat is not None and lon is not None:
            from app.services.kakao import coord_to_hcode
            hcode = coord_to_hcode(lat, lon, client=client)
            if hcode:
                adstrd_code = hcode[:8]

        if not adstrd_code or not str(adstrd_code).startswith("11"):
            return None, [f"생활인구: 서울 행정동코드(11…)만 지원 — '{adstrd_code}' 건너뜀."]

        ymd = date_id or _latest_date(key, client, cache=cache)
        if not ymd:
            return None, ["생활인구: 최신 가용일 확인 실패 — 건너뜀."]

        cache_key = make_key("seoul_pop", adstrd_code, ymd, hour)
        if cache:
            cached = cache.get(cache_key)
            if cached:
                return cached.get("data"), cached.get("notes", [])

        url = f"{_HOST}/{key}/json/{_SVC}/1/5/{ymd}/{hour}/{adstrd_code}"
        r = request_with_retry(client, "GET", url, timeout=15.0)
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
