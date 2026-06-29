"""부동산원 R-ONE 통계 — reb.or.kr OpenAPI (RONE_KEY, KEY= 방식).

지역별 부동산 통계지수(예: 아파트 매매가격지수)를 통계표ID로 조회.
지역명(CLS_NM)으로 매칭, 가장 최근 시점(WRTTIME) 값 반환.
값 없음/오류는 graceful (절대 원칙 3). 캐시 키: rone:{statbl}:{region}.
검증된 엔드포인트만 사용 (docs/API_VERIFICATION_2026-06-26).
"""

from __future__ import annotations

import os
from datetime import date
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key

_URL = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
# 기본 통계표: 월간 아파트 매매가격지수 (시군구). 검증된 STATBL_ID.
_DEFAULT_STATBL = "A_2024_00045"


def _key() -> str:
    k = os.getenv("RONE_KEY", "")
    if not k:
        raise ValueError("RONE_KEY 미설정")
    return k


def _rows(body: dict) -> List[dict]:
    """SttsApiTblData 응답 → row 리스트 (head/RESULT 제외)."""
    for k, v in body.items():
        if k == "RESULT" or not isinstance(v, list):
            continue
        for blk in v:
            if isinstance(blk, dict) and "row" in blk:
                return blk["row"]
    return []


def fetch_price_index(
    region_name: str,
    statbl_id: str = _DEFAULT_STATBL,
    cycle: str = "MM",
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """지역 부동산 통계지수 — 지역명 매칭, 최근 시점 값.

    Returns:
        ({value, period, region, item, statbl_id}, notes) 또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    cache_key = make_key("rone", statbl_id, region_name or "ALL")
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return cached.get("data"), cached.get("notes", [])

    # 최근 ~2년만 조회 (전체 시계열은 오래된 것부터라 최신이 안 잡힘)
    this_year = date.today().year
    own = client is None
    client = client or httpx.Client(timeout=20.0)
    try:
        r = client.get(
            _URL,
            params={"KEY": key, "STATBL_ID": statbl_id, "DTACYCLE_CD": cycle,
                    "Type": "json", "pIndex": 1, "pSize": 1000,
                    "START_WRTTIME": f"{this_year - 1}01", "END_WRTTIME": f"{this_year}12"},
            timeout=20.0,
        )
        r.raise_for_status()
        try:
            body = r.json()
        except Exception:
            return None, ["부동산원: 응답 형식 오류 (JSON 아님)."]

        res = body.get("RESULT", {})
        if isinstance(res, dict) and str(res.get("CODE", "")).startswith("ERROR"):
            return None, [f"부동산원: {res.get('CODE')} {res.get('MESSAGE', '')}".strip()]

        rows = _rows(body)
        if not rows:
            return None, [f"부동산원: {statbl_id} 데이터 없음."]

        # 지역명 매칭 (CLS_NM 에 region_name 포함). 없으면 전체에서 최신.
        cand = [r0 for r0 in rows if region_name and region_name in str(r0.get("CLS_NM", ""))]
        if not cand:
            cand = rows
            notes.append(f"부동산원: '{region_name}' 지역 매칭 없음 — 통계표 전체 최신값 사용(참고).")

        # 가장 최근 시점 (WRTTIME_IDTFR_ID = yyyymm)
        latest = max(cand, key=lambda r0: str(r0.get("WRTTIME_IDTFR_ID", "")))
        try:
            value = float(latest.get("DTA_VAL"))
        except (TypeError, ValueError):
            return None, ["부동산원: 값 파싱 실패."]

        data = {
            "value": value,
            "period": str(latest.get("WRTTIME_IDTFR_ID", "")),
            "region": str(latest.get("CLS_NM", "")),
            "item": str(latest.get("ITM_NM", "")),
            "statbl_id": statbl_id,
        }
        notes.append(f"부동산원: {data['region']} {data['item']} {data['period']} 기준 (R-ONE {statbl_id}).")
        if cache:
            cache.set(cache_key, {"data": data, "notes": notes})
        return data, notes

    except ValueError as e:
        return None, [str(e)]
    except Exception as e:
        return None, [f"부동산원 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()
