"""KOSIS 다차원 census 지표 fetch (차원 크랙 — docs/KOSIS_DEPTH_PLAN.md ①).

다차원 표(시군구×산업×규모 등)는 표마다 지역코드체계(census·KOSIS자체·롱코드)와 분류차원이 달라
범용질의(objL1=행안부코드)가 err21 난다. 해결: getMeta type=ITM 응답이 OBJ_NM 으로 모든 차원을
담는다 → 차원을 등장순서(=objL 순서)로 정렬, 지역차원에서 시군구 코드 + 분류차원의 '전체/계'
합계코드를 뽑아 objL1·objL2… 순서대로 질의 구성.

★동명 시군구(중구·동구·서구·남구·북구 — 광역시마다 존재) 오매칭 방지: 지역멤버에서 이름만으로
  고르지 않고, census 시도코드(2자리) prefix 로 site 시도와 일치하는 구를 선택 (sido 인자 필요).

값은 실제 KOSIS 호출 (절대 원칙 1). 시군구 평균이므로 호출부가 '○○구 기준' 표기 (절대 원칙 4).
실패는 graceful — None + notes (절대 원칙 3). 캐시: 메타·데이터 각각.
검증된 방법만 사용 (scripts/profile_kosis_dims.py 8/9 검증, docs/KOSIS_DEPTH_PLAN.md).
"""

from __future__ import annotations

import json
import os
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key
from app.services.http_retry import request_with_retry

_DATA = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
_META = "https://kosis.kr/openapi/statisticsData.do"

_REGION_HINTS = ("시군구", "행정구역", "시도", "지역", "시·군·구")
_TOTAL_NAMES = {"전체", "계", "합계", "총계", "소계", "전산업", "전국"}
_TOTAL_CODES = {"0", "00", "000", "TT"}
_PRD_PARAM = {"년": "Y", "월": "M", "분기": "Q", "5년": "F", "3년": "F"}


def _key() -> str:
    k = os.getenv("KOSIS_KEY")
    if not k:
        raise ValueError("KOSIS_KEY 미설정")
    return k


def _get_itm_meta(
    client: httpx.Client, key: str, org_id: str, tbl_id: str, cache: Optional[Cache]
) -> list:
    """getMeta type=ITM (차원·멤버 전체). 비지 않은 응답만 캐시 (일시적 빈값 영구화 방지)."""
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
    if cache and rows:  # 빈 응답은 캐시 안 함 (LOW 수정)
        cache.set(ckey, {"rows": rows})
    return rows


def _ordered_dims(itm_rows: list) -> List[dict]:
    """ITM 메타 → 차원 그룹 리스트 (등장순서 = KOSIS objL 순서 가정, MEDIUM 수정).

    각 dim: {obj_id, obj_nm, is_item, is_region, members[(code,name)], totals[code]}.
    """
    seen: dict = {}
    order: list = []
    for x in itm_rows:
        k = (x.get("OBJ_ID"), x.get("OBJ_NM"))
        if k not in seen:
            seen[k] = {"obj_id": k[0], "obj_nm": k[1] or "", "members": []}
            order.append(k)
        seen[k]["members"].append((x.get("ITM_ID"), x.get("ITM_NM")))
    dims: List[dict] = []
    for k in order:
        g = seen[k]
        onm = g["obj_nm"]
        g["is_item"] = onm == "항목" or g["obj_id"] == "ITEM"
        g["is_region"] = any(h in onm for h in _REGION_HINTS)
        g["totals"] = [m for m, n in g["members"]
                       if m in _TOTAL_CODES or (n and n.strip() in _TOTAL_NAMES)]
        dims.append(g)
    return dims


def _pick_region(members: list, city_name: str, sido: str) -> Optional[str]:
    """지역멤버에서 시군구 코드 선택. 동명 다수면 census 시도prefix로 disambiguate (HIGH 수정).

    census 코드 2자리 = census 시도코드(행안부와 다름 — 부산 행안부26≠census21). 지역멤버에
    포함된 시도레벨 항목(2자리코드 → 시도명)으로 site 시도와 매칭해 올바른 구를 고른다.
    """
    cands = [(m, n) for m, n in members if (n or "").strip() == city_name]
    if not cands:  # 정확일치 없으면 startswith 폴백
        cands = [(m, n) for m, n in members if (n or "").strip().startswith(city_name)]
    if not cands:
        return None
    if len(cands) == 1 or not sido:
        return cands[0][0]

    # 동명 다수 → census 시도prefix(2자리) → 시도명 맵 만들어 site 시도와 일치하는 구 선택
    sido_prefix = {
        (m or "").strip(): (n or "").strip()
        for m, n in members
        if (m or "").strip().isdigit() and len((m or "").strip()) == 2
    }
    key2 = sido.strip()[:2]  # 시도명 앞 2글자 (예: '부산'·'대전')
    target = next((p for p, nm in sido_prefix.items() if key2 and key2 in nm), None)
    if target:
        hit = next((m for m, n in cands if (m or "").startswith(target)), None)
        if hit:
            return hit
    return cands[0][0]  # 못 가리면 첫째 (그대로, graceful)


def fetch_census_indicator(
    org_id: str,
    tbl_id: str,
    itm_id: str,
    city_name: str,
    prd_se: str = "년",
    *,
    sido: str = "",
    breakdown: bool = False,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """다차원 census 표에서 시군구 값 1개 (+선택 분류구성 교차).

    sido: 동명 시군구 disambiguation 용 시도명 (예: '부산'·'대전'). 없으면 이름만 매칭(동명 위험).
    Returns:
        ({value, year, breakdown?[(분류명,값)]}, notes) 또는 (None, notes).
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [f"{tbl_id}: KOSIS 키 오류 ({e})"]

    own = client is None
    client = client or httpx.Client(timeout=25.0)
    try:
        itm_rows = _get_itm_meta(client, key, org_id, tbl_id, cache)
        if not itm_rows:
            return None, [f"{tbl_id}: 메타 없음 — 건너뜀."]
        dims = _ordered_dims(itm_rows)
        region_dim = next((d for d in dims if d["is_region"]), None)
        if not region_dim:
            return None, [f"{tbl_id}: 지역차원 없음 — 건너뜀."]
        region_code = _pick_region(region_dim["members"], city_name, sido)
        if not region_code:
            return None, [f"{tbl_id}: '{sido} {city_name}'.strip() 지역코드 미확인 — 건너뜀."]

        # objL 순서 = 비-항목 차원 등장순서 (region·분류 모두 포함). 합계코드로 그랜드토탈.
        prd = _PRD_PARAM.get(prd_se, "Y")
        params = {
            "method": "getList", "apiKey": key, "format": "json", "jsonVD": "Y",
            "orgId": org_id, "tblId": tbl_id, "itmId": itm_id,
            "prdSe": prd, "newEstPrdCnt": "1",
        }
        objl_vals: List[str] = []
        breakdown_pos: Optional[int] = None  # 분류구성 교차할 objL 위치
        pos = 1
        for d in dims:
            if d["is_item"]:
                continue
            if d["is_region"]:
                val = region_code
            else:
                val = d["totals"][0] if d["totals"] else "ALL"
                if breakdown_pos is None:
                    breakdown_pos = pos  # 첫 분류차원 = 교차 대상
            params[f"objL{pos}"] = val
            objl_vals.append(val)
            pos += 1

        ckey = make_key("kosis_cm", org_id, tbl_id, itm_id, prd, "|".join(objl_vals))
        cached = cache.get(ckey) if cache else None
        if cached is not None:
            data = cached.get("data")
        else:
            r = request_with_retry(client, "GET", _DATA, params=params, timeout=25.0)
            d_json = json.loads(r.text)
            if not (isinstance(d_json, list) and d_json):
                err = d_json.get("err") if isinstance(d_json, dict) else "무자료"
                return None, [f"{tbl_id}: 조회 실패(err{err}) — 건너뜀."]
            row = d_json[0]
            try:
                value = int(float(row["DT"]))
            except (KeyError, TypeError, ValueError):
                return None, [f"{tbl_id}: 값 파싱 실패 — 건너뜀."]
            data = {"value": value, "year": row.get("PRD_DE")}
            if cache:
                cache.set(ckey, {"data": data})

        # 분류구성 교차 (예: 산업대분류별) — 첫 분류차원을 ALL 로 펼쳐 상위 구성 추출
        if breakdown and data and breakdown_pos is not None:
            bparams = dict(params)
            bparams[f"objL{breakdown_pos}"] = "ALL"
            bkey = make_key("kosis_cmbd", org_id, tbl_id, itm_id, prd, "|".join(objl_vals), str(breakdown_pos))
            bcached = cache.get(bkey) if cache else None
            if bcached is not None:
                data = {**data, "breakdown": bcached.get("breakdown", [])}
            else:
                rb = request_with_retry(client, "GET", _DATA, params=bparams, timeout=25.0)
                db = json.loads(rb.text)
                if isinstance(db, list):
                    ccol = f"C{breakdown_pos}"
                    tops = sorted(
                        [x for x in db if x.get(ccol) not in ("0", None) and x.get("DT")],
                        key=lambda x: -float(x["DT"]),
                    )[:5]
                    bd = [[x.get(f"{ccol}_NM"), int(float(x["DT"]))] for x in tops]
                    data = {**data, "breakdown": bd}
                    if cache:
                        cache.set(bkey, {"breakdown": bd})

        return data, notes
    except Exception as e:  # noqa: BLE001 — 한 지표 실패가 전체를 막지 않게
        return None, [f"{tbl_id}: 예외 ({type(e).__name__})"]
    finally:
        if own:
            client.close()
