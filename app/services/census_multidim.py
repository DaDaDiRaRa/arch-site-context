"""KOSIS 다차원 census 지표 fetch (차원 크랙 — docs/KOSIS_DEPTH_PLAN.md ①).

다차원 표(시군구×산업×규모 등)는 표마다 지역코드체계(census·KOSIS자체·롱코드)와 분류차원이 달라
범용질의(objL1=행안부코드)가 err21 난다. 해결: getMeta type=ITM 응답이 OBJ_NM 으로 모든 차원을
담는다 → 지역차원에서 시군구 코드(이름매칭) + 분류차원의 '전체/계' 합계코드를 뽑아 질의 구성.

값은 실제 KOSIS 호출 (절대 원칙 1). 시군구 평균이므로 호출부가 '○○구 기준' 표기 (절대 원칙 4).
실패는 graceful — None + notes (절대 원칙 3). 캐시: 메타·데이터 각각.
검증된 방법만 사용 (scripts/profile_kosis_dims.py 8/9 검증, docs/KOSIS_DEPTH_PLAN.md).
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key
from app.services.http_retry import request_with_retry
from app.services.kosis import _key  # 동일 KOSIS 키 재사용

_DATA = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
_META = "https://kosis.kr/openapi/statisticsData.do"

_REGION_HINTS = ("시군구", "행정구역", "시도", "지역", "시·군·구")
_TOTAL_NAMES = {"전체", "계", "합계", "총계", "소계", "전산업", "전국"}
_TOTAL_CODES = {"0", "00", "000", "TT"}
_PRD_PARAM = {"년": "Y", "월": "M", "분기": "Q", "5년": "F", "3년": "F"}


def _get_itm_meta(
    client: httpx.Client, key: str, org_id: str, tbl_id: str, cache: Optional[Cache]
) -> list:
    """getMeta type=ITM (차원·멤버 전체). 캐시 — 동일 표 1회."""
    ckey = make_key("kosis_itmmeta", org_id, tbl_id)
    if cache:
        c = cache.get(ckey)
        if c is not None:
            return c.get("rows", [])
    r = request_with_retry(client, "GET", _META, params={
        "method": "getMeta", "apiKey": key, "format": "json", "jsonVD": "Y",
        "orgId": org_id, "tblId": tbl_id, "type": "ITM"}, timeout=25.0)
    rows = json.loads(r.text)
    rows = rows if isinstance(rows, list) else []
    if cache:
        cache.set(ckey, {"rows": rows})
    return rows


def _resolve_dims(itm_rows: list, city_name: str) -> Tuple[Optional[str], List[str]]:
    """ITM 메타 → (해당 시군구 지역코드, 분류차원별 합계코드 리스트). 못 찾으면 (None, [])."""
    by_obj: dict = defaultdict(list)
    for x in itm_rows:
        by_obj[(x.get("OBJ_ID"), x.get("OBJ_NM"))].append((x.get("ITM_ID"), x.get("ITM_NM")))

    region_code: Optional[str] = None
    classification_totals: List[str] = []
    for (oid, onm), members in by_obj.items():
        if any(h in (onm or "") for h in _REGION_HINTS):
            # 지역차원 — 이름이 city_name 으로 시작하는 멤버 (예: '영등포구')
            region_code = next(
                (m for m, n in members if (n or "").strip().startswith(city_name)), None
            )
        elif onm != "항목" and oid != "ITEM":
            # 분류차원 — '전체/계' 합계코드. 없으면 ALL(서버 합산).
            totals = [m for m, n in members if m in _TOTAL_CODES or (n and n.strip() in _TOTAL_NAMES)]
            classification_totals.append(totals[0] if totals else "ALL")
    return region_code, classification_totals


def fetch_census_indicator(
    org_id: str,
    tbl_id: str,
    itm_id: str,
    city_name: str,
    prd_se: str = "년",
    *,
    breakdown: bool = False,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """다차원 census 표에서 시군구 값 1개 (+선택 분류구성 교차).

    Returns:
        ({value, year, breakdown?[(분류명,값)]}, notes) 또는 (None, notes).
    """
    notes: List[str] = []
    try:
        key = _key()
    except Exception as e:  # noqa: BLE001 — KosisError 등
        return None, [f"{tbl_id}: KOSIS 키 오류 ({e})"]

    own = client is None
    client = client or httpx.Client(timeout=25.0)
    try:
        itm_rows = _get_itm_meta(client, key, org_id, tbl_id, cache)
        if not itm_rows:
            return None, [f"{tbl_id}: 메타 없음 — 건너뜀."]
        region_code, totals = _resolve_dims(itm_rows, city_name)
        if not region_code:
            return None, [f"{tbl_id}: '{city_name}' 지역코드 미확인 — 건너뜀."]

        prd = _PRD_PARAM.get(prd_se, "Y")
        params = {
            "method": "getList", "apiKey": key, "format": "json", "jsonVD": "Y",
            "orgId": org_id, "tblId": tbl_id, "itmId": itm_id,
            "objL1": region_code, "prdSe": prd, "newEstPrdCnt": "1",
        }
        for i, tot in enumerate(totals):
            params[f"objL{i + 2}"] = tot

        ckey = make_key("kosis_cm", org_id, tbl_id, itm_id, region_code, prd, "|".join(totals))
        cached = cache.get(ckey) if cache else None
        if cached is not None:
            data = cached.get("data")
        else:
            r = request_with_retry(client, "GET", _DATA, params=params, timeout=25.0)
            d = json.loads(r.text)
            if not (isinstance(d, list) and d):
                err = d.get("err") if isinstance(d, dict) else "무자료"
                return None, [f"{tbl_id}: 조회 실패(err{err}) — 건너뜀."]
            row = d[0]
            try:
                value = int(float(row["DT"]))
            except (KeyError, TypeError, ValueError):
                return None, [f"{tbl_id}: 값 파싱 실패 — 건너뜀."]
            data = {"value": value, "year": row.get("PRD_DE")}
            if cache:
                cache.set(ckey, {"data": data})

        # 분류구성 교차 (예: 산업대분류별) — breakdown 요청 시 objL2=ALL 재호출
        if breakdown and data:
            bparams = dict(params)
            bparams["objL2"] = "ALL"
            bkey = make_key("kosis_cmbd", org_id, tbl_id, itm_id, region_code, prd)
            bcached = cache.get(bkey) if cache else None
            if bcached is not None:
                data = {**data, "breakdown": bcached.get("breakdown", [])}
            else:
                rb = request_with_retry(client, "GET", _DATA, params=bparams, timeout=25.0)
                db = json.loads(rb.text)
                if isinstance(db, list):
                    tops = sorted(
                        [x for x in db if x.get("C2") not in ("0", None) and x.get("DT")],
                        key=lambda x: -float(x["DT"]),
                    )[:5]
                    bd = [[x.get("C2_NM"), int(float(x["DT"]))] for x in tops]
                    data = {**data, "breakdown": bd}
                    if cache:
                        cache.set(bkey, {"breakdown": bd})

        return data, notes
    except Exception as e:  # noqa: BLE001 — 한 지표 실패가 전체를 막지 않게
        return None, [f"{tbl_id}: 예외 ({type(e).__name__})"]
    finally:
        if own:
            client.close()
