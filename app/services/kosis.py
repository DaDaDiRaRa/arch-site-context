"""KOSIS OpenAPI 클라이언트 (모드 A, P5).

값은 실제 KOSIS에서 호출해 가져온다 (절대 원칙 1). HTTPS 필수.
'지역단위로 묶어' 한 (orgId,tblId,지역,연도)당 1회 호출 → 캐시. 분당 제한 대응.
지역코드(objL1) = 행정구역코드 = P1.6 resolve 의 sgg_code (검증됨).
"""

from __future__ import annotations

import os
from typing import List, Optional

import httpx

from app.services.cache import Cache, default_cache, make_key

_BASE = "https://kosis.kr/openapi/Param/statisticsParameterData.do"

# 실제 네트워크 호출 횟수 (캐시 히트 검증용 — 테스트가 0콜을 확인).
NETWORK_CALLS = 0


class KosisError(RuntimeError):
    """KOSIS 호출 실패 / 데이터 없음."""


def _key() -> str:
    k = os.getenv("KOSIS_KEY")
    if not k:
        raise KosisError("KOSIS_KEY 가 설정되지 않았습니다 (.env 확인).")
    return k


def _normalize(rows: list) -> List[dict]:
    """KOSIS 원본 행 → 표준 행 {itm_id, c2, c2_nm, value, unit, prd_de}."""
    out: List[dict] = []
    for r in rows:
        dt = r.get("DT")
        try:
            value = float(dt)
        except (TypeError, ValueError):
            value = None  # '-', '', None 등 결측 → None
        out.append(
            {
                "itm_id": r.get("ITM_ID"),
                "c2": r.get("C2"),
                "c2_nm": r.get("C2_NM"),
                "value": value,
                "unit": r.get("UNIT_NM"),
                "prd_de": r.get("PRD_DE"),
            }
        )
    return out


def fetch_table(
    org_id: str,
    tbl_id: str,
    region_code: str,
    year: Optional[int] = None,
    *,
    itm_id: str = "ALL",
    obj_l2: Optional[str] = None,
    cache: Optional[Cache] = None,
) -> dict:
    """한 (orgId,tblId,지역,연도) 조회. 캐시 우선, 없을 때만 1회 네트워크.

    반환: {"rows": [표준행...], "year": 실제연도}. 데이터 없으면 KosisError.
    """
    cache = cache if cache is not None else default_cache
    ckey = make_key("kosis", org_id, tbl_id, region_code, year or "latest", itm_id, obj_l2)

    cached = cache.get(ckey)
    if cached is not None:
        return cached  # 캐시 히트 — 네트워크 0콜

    params = {
        "method": "getList",
        "apiKey": _key(),
        "format": "json",
        "jsonVD": "Y",
        "orgId": org_id,
        "tblId": tbl_id,
        "itmId": itm_id,
        "objL1": region_code,
        "prdSe": "Y",
    }
    if obj_l2 is not None:
        params["objL2"] = obj_l2
    if year is not None:
        params["startPrdDe"] = str(year)
        params["endPrdDe"] = str(year)
    else:
        params["newEstPrdCnt"] = "1"

    global NETWORK_CALLS
    NETWORK_CALLS += 1
    try:
        r = httpx.get(_BASE, params=params, timeout=25.0)
    except Exception as e:
        raise KosisError(f"KOSIS 네트워크 오류: {e}")

    import json as _json

    try:
        data = _json.loads(r.text)
    except Exception:
        raise KosisError(f"KOSIS 응답 파싱 실패: {r.text[:200]}")

    if isinstance(data, dict):  # 에러는 dict {err, errMsg}
        raise KosisError(f"KOSIS 오류 {data.get('err')}: {data.get('errMsg')}")
    if not data:
        raise KosisError(f"KOSIS 데이터 없음 (tbl={tbl_id}, 지역={region_code}, 연도={year})")

    rows = _normalize(data)
    year_used = year if year is not None else _latest_year(rows)
    result = {"rows": rows, "year": year_used}
    cache.set(ckey, result)
    return result


def _latest_year(rows: List[dict]) -> Optional[int]:
    years = [int(r["prd_de"]) for r in rows if r.get("prd_de") and r["prd_de"].isdigit()]
    return max(years) if years else None


# ─────────────────────────────────────────────────────────────────────────────
# census 지역코드 리졸버 (인구총조사 등)
#
# 주민등록 테이블(DT_1B04005N)은 행안부 시군구코드(영등포구=11560)를 그대로 쓰지만,
# 인구총조사 계열 테이블은 통계청 census 지역코드(영등포구=11190)를 써서 코드가 다르다.
# 둘은 시도 2자리 접두만 공유(서울=11)하므로, 테이블 자신의 지역목록(objL1=ALL)을 1회
# 호출(캐시)해 '시도접두 + 시군구명'으로 census 코드를 역추출한다 (추정 아님, 절대 원칙 1·3).
# ─────────────────────────────────────────────────────────────────────────────


def _region_map(
    org_id: str, tbl_id: str, obj_l2: Optional[str], cache: Cache
) -> dict:
    """테이블의 지역목록 {"시도접두|지역명": C1코드}. 캐시 우선, 없을 때만 1회 호출."""
    ckey = make_key("kosis_regmap", org_id, tbl_id, obj_l2)
    cached = cache.get(ckey)
    if cached is not None:
        return cached

    params = {
        "method": "getList",
        "apiKey": _key(),
        "format": "json",
        "jsonVD": "Y",
        "orgId": org_id,
        "tblId": tbl_id,
        "itmId": "ALL",
        "objL1": "ALL",
        "prdSe": "Y",
        "newEstPrdCnt": "1",
    }
    if obj_l2 is not None:
        params["objL2"] = obj_l2

    global NETWORK_CALLS
    NETWORK_CALLS += 1
    try:
        r = httpx.get(_BASE, params=params, timeout=25.0)
    except Exception as e:
        raise KosisError(f"KOSIS 지역목록 네트워크 오류: {e}")

    import json as _json

    try:
        data = _json.loads(r.text)
    except Exception:
        raise KosisError(f"KOSIS 지역목록 파싱 실패: {r.text[:200]}")
    if isinstance(data, dict):
        raise KosisError(f"KOSIS 지역목록 오류 {data.get('err')}: {data.get('errMsg')}")

    out: dict = {}
    for row in data:
        c1 = row.get("C1")
        nm = row.get("C1_NM")
        if c1 and nm:
            out.setdefault(f"{c1[:2]}|{nm}", c1)
    cache.set(ckey, out)
    return out


def resolve_census_region(
    org_id: str,
    tbl_id: str,
    sido_prefix: str,
    sigungu_name: str,
    *,
    obj_l2: Optional[str] = None,
    cache: Optional[Cache] = None,
) -> Optional[str]:
    """행안부 시군구명 → 이 테이블의 census 지역코드. 못 찾으면 None (추정 금지)."""
    cache = cache if cache is not None else default_cache
    m = _region_map(org_id, tbl_id, obj_l2, cache)
    return m.get(f"{sido_prefix}|{sigungu_name}")
