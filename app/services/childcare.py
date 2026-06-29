"""어린이집 현황 — 정보공개포털 (CHILDCARE_INFO_KEY).

시군구코드(arcode = resolve sgg_code 5자리) → 어린이집 개수·총정원 집계.
cpmsapi021("어린이집별 정보 조회", XML). 좌표 없음(주소만) — 시군구 단위 공급 지표.
카카오 키워드엔 없는 **정원(crcapat)** 합계가 고유값 (수급진단 공급 capacity).
값 없음/오류는 graceful (절대 원칙 3). 캐시 키: childcare:{arcode}.
검증된 엔드포인트만 사용 ([[childcare-culture-api]], 2026-06-29 실호출).
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key
from app.services.http_retry import request_with_retry

_URL = "http://api.childcare.go.kr/mediate/rest/cpmsapi021/cpmsapi021/request"

# 정보공개포털 오류코드 (명세서 §4). INFO-200(결과없음)은 정상 0건 취급.
_ERR_MSG = {
    "ERROR-100": "필수값 누락",
    "ERROR-200": "서버 오류",
    "INFO-100": "인증키 무효",
    "INFO-300": "요청건수 초과",
    "INFO-400": "인증키 만료",
}


def _key() -> str:
    k = os.getenv("CHILDCARE_INFO_KEY", "")
    if not k:
        raise ValueError("CHILDCARE_INFO_KEY 미설정")
    return k


def fetch_childcare(
    sgg_code: str,
    region_name: str = "",
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """시군구 어린이집 개수·총정원 집계 (arcode = sgg_code 5자리).

    region_name: notes/scope 라벨용 시군구명(선택). 없으면 코드 표기.
    Returns:
        ({count, total_capacity, sample[어린이집명], scope}, notes) 또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    arcode = (sgg_code or "").strip()
    if len(arcode) != 5 or not arcode.isdigit():
        return None, [f"어린이집: 시군구코드 형식 오류 ('{sgg_code}') — 건너뜀."]

    scope = region_name or arcode
    cache_key = make_key("childcare", arcode)
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return cached.get("data"), cached.get("notes", [])

    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        r = request_with_retry(
            client, "GET", _URL, params={"key": key, "arcode": arcode}, timeout=15.0
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)

        errcode = root.findtext("errcode")
        if errcode:
            if errcode == "INFO-200":  # 검색결과 없음 — 정상 0건
                data = {"count": 0, "total_capacity": 0, "sample": [], "scope": scope}
                notes.append(f"어린이집: {scope} 0건 (정보공개포털).")
                if cache:
                    cache.set(cache_key, {"data": data, "notes": notes})
                return data, notes
            desc = _ERR_MSG.get(errcode, errcode)
            return None, [f"어린이집: 정보공개포털 오류 {errcode}({desc})."]

        items = root.findall("item")
        if not items:
            return None, [f"어린이집: {scope} 데이터 없음."]

        total_cap = 0
        names: List[str] = []
        for it in items:
            cap = (it.findtext("crcapat") or "").strip()
            if cap.isdigit():
                total_cap += int(cap)
            nm = (it.findtext("crname") or "").strip()
            if nm:
                names.append(nm)

        data = {
            "count": len(items),
            "total_capacity": total_cap,
            "sample": names[:5],
            "scope": scope,
        }
        notes.append(
            f"어린이집: {scope} {len(items)}개·정원 {total_cap}명 "
            f"(정보공개포털, 시군구 기준 — 참고)."
        )
        if cache:
            cache.set(cache_key, {"data": data, "notes": notes})
        return data, notes

    except ET.ParseError as e:
        return None, [f"어린이집: 응답 파싱 실패 ({str(e)[:80]})."]
    except ValueError as e:
        return None, [str(e)]
    except Exception as e:
        return None, [f"어린이집(정보공개포털) 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()
