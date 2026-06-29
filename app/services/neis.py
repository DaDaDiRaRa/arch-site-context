"""학교 현황 — NEIS 교육정보 개방 포털 (NEIS_KEY).

시도(교육청)별 학교 목록 → 시군구(도로명주소) 필터 + 학교종류별 집계.
값 없음/오류는 graceful (절대 원칙 3). 캐시 키: neis:{sido}:{sigungu}:{level}.
검증된 엔드포인트만 사용 (docs/API_VERIFICATION_2026-06-26).
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key

_URL = "https://open.neis.go.kr/hub/schoolInfo"

# 시도명 → 시도교육청 코드(ATPT_OFCDC_SC_CODE)
_OFC_CODE = {
    "서울특별시": "B10", "부산광역시": "C10", "대구광역시": "D10", "인천광역시": "E10",
    "광주광역시": "F10", "대전광역시": "G10", "울산광역시": "H10", "세종특별자치시": "I10",
    "경기도": "J10", "강원특별자치도": "K10", "강원도": "K10", "충청북도": "M10",
    "충청남도": "N10", "전라북도": "P10", "전북특별자치도": "P10", "전라남도": "Q10",
    "경상북도": "R10", "경상남도": "S10", "제주특별자치도": "T10",
}
_PSIZE = 1000
_MAX_PAGES = 3


def _key() -> str:
    k = os.getenv("NEIS_KEY", "")
    if not k:
        raise ValueError("NEIS_KEY 미설정")
    return k


def fetch_schools(
    sido: str,
    sigungu: str = "",
    level: str = "",
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """시도(+시군구) 학교 수·종류별 집계.

    level: '초등학교'|'중학교'|'고등학교' 등 SCHUL_KND_SC_NM 필터(선택).
    Returns:
        ({count, by_level{종류:수}, sample[학교명], scope}, notes) 또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    ofc = _OFC_CODE.get(sido)
    if not ofc:
        return None, [f"학교: 시도교육청 코드 미확인 ('{sido}') — 건너뜀."]

    cache_key = make_key("neis", sido, sigungu or "ALL", level or "ALL")
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return cached.get("data"), cached.get("notes", [])

    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        rows: List[dict] = []
        for page in range(1, _MAX_PAGES + 1):
            params = {"KEY": key, "Type": "json", "pIndex": page, "pSize": _PSIZE,
                      "ATPT_OFCDC_SC_CODE": ofc}
            if level:
                params["SCHUL_KND_SC_NM"] = level
            r = client.get(_URL, params=params, timeout=15.0)
            r.raise_for_status()
            j = r.json()
            if "schoolInfo" not in j:
                code = j.get("RESULT", {}).get("CODE", "")
                if code == "INFO-200":  # 해당 없음
                    break
                return None, [f"학교: NEIS 응답 오류 ({code or '형식'})."]
            page_rows = j["schoolInfo"][1].get("row", []) or []
            rows.extend(page_rows)
            total = j["schoolInfo"][0]["head"][0]["list_total_count"]
            if page * _PSIZE >= total:
                break

        if not rows:
            return None, [f"학교: {sido} 데이터 없음."]

        # 시군구 필터 (도로명주소 ORG_RDNMA 에 시군구 포함)
        scope = sido
        if sigungu:
            rows = [r0 for r0 in rows if sigungu in (r0.get("ORG_RDNMA") or "")]
            scope = f"{sido} {sigungu}"

        by_level: dict = {}
        for r0 in rows:
            knd = r0.get("SCHUL_KND_SC_NM", "기타")
            by_level[knd] = by_level.get(knd, 0) + 1

        data = {
            "count": len(rows),
            "by_level": by_level,
            "sample": [r0.get("SCHUL_NM", "") for r0 in rows[:5]],
            "scope": scope,
        }
        notes.append(f"학교: {scope} {len(rows)}교 (NEIS, 도로명주소 기준 집계 — 참고).")
        if cache:
            cache.set(cache_key, {"data": data, "notes": notes})
        return data, notes

    except ValueError as e:
        return None, [str(e)]
    except Exception as e:
        return None, [f"학교(NEIS) 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()
