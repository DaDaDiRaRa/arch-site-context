"""문화기반시설 — 전국문화기반시설총람 (data.go.kr B553457, DATA_GO_KR_API_KEY).

시군구코드(sggCd = resolve sgg_code 5자리) → 10개 시설유형별 개수·시설명 집계.
문화체육관광부가 매년 발간하는 총람. 시설유형마다 operation 분리(전부 동일 파라미터).
필수: serviceKey + pblshYr(발간연도). pblshYr 미지정 시 최신연도 자동탐지.
좌표 없음(주소만) — 시군구 단위 문화 인프라 지표.
값 없음/오류는 graceful (절대 원칙 3). 캐시 키: culture:{sggCd}:{pblshYr}.
검증된 엔드포인트·필드만 사용 ([[childcare-culture-api]], 2026-06-29 실호출).
"""

from __future__ import annotations

import os
from datetime import date
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key
from app.services.http_retry import request_with_retry

_BASE = "https://apis.data.go.kr/B553457/rgnCltrFcltExmnv1"

# (operation, 시설유형, 시설명 필드). 주소는 instAddr, 단 문학관만 addr (실호출 확인).
_OPS = [
    ("clifLtrm1", "문학관", "ltrmNm"),
    ("clifMsmv1", "박물관", "msmNm"),
    ("clifArglv1", "미술관", "arglNm"),
    ("clifClcnv1", "문예회관", "clcnNm"),
    ("clifNtnLbrryv1", "국립도서관", "lbrryNm"),
    ("clifLbrryv1", "공공도서관", "lbrryNm"),
    ("clifLvclCntrv1", "생활문화센터", "lvclCntrNm"),
    ("clifLclcv1", "지방문화원", "lclcNm"),
    ("clifClhsv1", "문화의집", "clhsNm"),
    ("clifLcclFndtv1", "지역문화재단", "lcclFndtNm"),
]
_NUM_ROWS = 100  # 시군구 한 유형 거의 전부 (count 는 totalCount 로 정확 보고)
_SAMPLE_MAX = 10


def _key() -> str:
    k = os.getenv("DATA_GO_KR_API_KEY", "")
    if not k:
        raise ValueError("DATA_GO_KR_API_KEY 미설정")
    return k


def _to_int(v: object) -> int:
    s = str(v or "0").strip()
    return int(s) if s.isdigit() else 0


def _latest_year(client: httpx.Client, key: str, cache: Optional[Cache]) -> Optional[str]:
    """최신 발간연도 탐지 — 공공도서관(전국 다수)으로 올해부터 역순, totalCount>0 첫 해.

    캐시 키에 올해를 포함 → 해가 바뀌면 자동 재탐지 (TTL 없는 파일캐시 보정).
    """
    this = date.today().year
    ck = make_key("culture_latest", this)
    if cache:
        c = cache.get(ck)
        if c and c.get("year"):
            return c["year"]
    for yr in range(this, this - 4, -1):
        try:
            r = request_with_retry(
                client, "GET", f"{_BASE}/clifLbrryv1",
                params={"serviceKey": key, "pblshYr": str(yr),
                        "resultType": "json", "numOfRows": 1},
                timeout=12.0,
            )
            body = (r.json().get("response", {}) or {}).get("body", {}) or {}
            if _to_int(body.get("totalCount")) > 0:
                if cache:
                    cache.set(ck, {"year": str(yr)})
                return str(yr)
        except Exception:
            continue
    return None


def _fetch_op(
    client: httpx.Client, key: str, op: str, yr: str, sgg: str,
    label: str, nm_field: str,
) -> Tuple[Optional[int], List[dict]]:
    """단일 시설유형 조회 → (count, [{type,name,addr}]). 실패 시 (None, [])."""
    try:
        r = request_with_retry(
            client, "GET", f"{_BASE}/{op}",
            params={"serviceKey": key, "pblshYr": yr, "sggCd": sgg,
                    "resultType": "json", "numOfRows": _NUM_ROWS},
            timeout=15.0,
        )
        r.raise_for_status()
        resp = r.json().get("response", {}) or {}
        if (resp.get("header", {}) or {}).get("resultCode") != "00":
            return None, []
        body = resp.get("body", {}) or {}
        count = _to_int(body.get("totalCount"))
        items: List[dict] = []
        for d in body.get("data", []) or []:
            nm = (d.get(nm_field) or "").strip()
            if not nm:
                continue
            addr = (d.get("instAddr") or d.get("addr") or "").strip()
            items.append({"type": label, "name": nm, "addr": addr})
        return count, items
    except Exception:
        return None, []


def fetch_culture(
    sgg_code: str,
    region_name: str = "",
    pblshYr: Optional[str] = None,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """시군구 문화기반시설 10종 집계 (sggCd = sgg_code 5자리).

    region_name: notes/scope 라벨용 시군구명(선택). pblshYr 미지정 시 자동탐지.
    Returns:
        ({pblshYr, total, by_type{유형:수}, sample[{type,name,addr}], scope}, notes)
        또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    sgg = (sgg_code or "").strip()
    if len(sgg) != 5 or not sgg.isdigit():
        return None, [f"문화시설: 시군구코드 형식 오류 ('{sgg_code}') — 건너뜀."]

    scope = region_name or sgg
    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        yr = pblshYr or _latest_year(client, key, cache)
        if not yr:
            return None, ["문화시설: 발간연도 확인 불가 (총람 응답 없음)."]

        cache_key = make_key("culture", sgg, yr)
        if cache:
            cached = cache.get(cache_key)
            if cached:
                return cached.get("data"), cached.get("notes", [])

        by_type: dict = {}
        facilities: List[dict] = []
        failed: List[str] = []
        for op, label, nm_field in _OPS:
            count, items = _fetch_op(client, key, op, yr, sgg, label, nm_field)
            if count is None:
                failed.append(label)
                continue
            if count > 0:
                by_type[label] = count
                facilities.extend(items)

        if not by_type and failed:
            return None, [f"문화시설: {scope} 전 유형 조회 실패 ({len(failed)}종)."]

        data = {
            "pblshYr": yr,
            "total": sum(by_type.values()),
            "by_type": by_type,
            "sample": facilities[:_SAMPLE_MAX],
            "scope": scope,
        }
        note = (f"문화시설: {scope} {data['total']}개 "
                f"(문화기반시설총람 {yr} 발간, 시군구 기준 — 참고).")
        if failed:
            note += f" 조회실패 {len(failed)}종: {','.join(failed)}."
        notes.append(note)
        if cache:
            cache.set(cache_key, {"data": data, "notes": notes})
        return data, notes

    except ValueError as e:
        return None, [str(e)]
    except Exception as e:
        return None, [f"문화시설(총람) 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()
