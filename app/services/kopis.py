"""공연시설 — KOPIS 공연예술통합전산망 OpenAPI (KOPIS_KEY).

prfplc(공연시설 목록) → 시설명·지역·공연장수. XML 응답.
⚠️ 현재 키가 returncode 02(SERVICE KEY NOT REGISTERED)로 거부됨(2026-06-29) — 재등록 필요.
   골격은 완성, 키 활성화 시 바로 작동. 오류는 graceful (절대 원칙 3).

★시군구 매핑: KOPIS signgucode(자체 코드체계)는 키가 죽어 실API로 검증 불가 →
  추정하지 않고(절대 원칙 3) **응답의 sidonm/gugunnm 이름으로 필터**한다(코드표 불필요·견고).
  검증된 KOPIS 시군구코드가 확보되면 signgucode 인자로 서버측 필터(효율) 추가 가능.
캐시 키: kopis:{sido}:{sigungu}:{signgucode}.
검증된 엔드포인트만 사용 (docs/API_VERIFICATION_2026-06-26).
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key
from app.services.http_retry import request_with_retry

_URL = "http://www.kopis.or.kr/openApi/restful/prfplc"
_ROWS = 100
_MAX_PAGES = 10  # 시군구 이름필터용 전국 페이징 상한 (= 최대 1000건)


def _key() -> str:
    k = os.getenv("KOPIS_KEY", "")
    if not k:
        raise ValueError("KOPIS_KEY 미설정")
    return k


def _parse_db(d: ET.Element) -> dict:
    return {
        "name": (d.findtext("fcltynm") or "").strip(),
        "sido": (d.findtext("sidonm") or "").strip(),
        "gugun": (d.findtext("gugunnm") or "").strip(),
        "id": (d.findtext("mt10id") or "").strip(),
        "hall_count": _int_or_none(d.findtext("mt13cnt")),
    }


def fetch_venues(
    sido: str = "",
    sigungu: str = "",
    signgucode: Optional[str] = None,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """공연시설 목록 — 시군구명(gugunnm) 필터.

    sigungu 지정 시: 전국 페이징(상한 _MAX_PAGES) 후 gugunnm 일치분만(+sido 일치 시 교차).
    signgucode 지정 시: 검증된 KOPIS 코드로 서버측 필터(이름필터 생략).
    Returns:
        ({count, scope, venues[{name, sido, gugun, id, hall_count}]}, notes) 또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    cache_key = make_key("kopis", sido or "ALL", sigungu or "ALL", signgucode or "")
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return cached.get("data"), cached.get("notes", [])

    # signgucode(서버필터) 있으면 1회, 없고 sigungu 이름필터면 페이징, 둘 다 없으면 1페이지.
    name_filter = bool(sigungu) and not signgucode
    max_pages = _MAX_PAGES if name_filter else 1

    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        venues: List[dict] = []
        truncated = False
        for cpage in range(1, max_pages + 1):
            params = {"service": key, "cpage": cpage, "rows": _ROWS}
            if signgucode:
                params["signgucode"] = signgucode
            r = request_with_retry(client, "GET", _URL, params=params, timeout=15.0)
            r.raise_for_status()
            try:
                root = ET.fromstring(r.text)
            except ET.ParseError:
                return None, ["공연시설: 응답 형식 오류 (XML 아님)."]

            rc = root.findtext(".//returncode")
            if rc and rc != "00":
                msg = root.findtext(".//errmsg") or ""
                if rc == "02":
                    return None, ["공연시설: KOPIS 키 미등록(returncode 02) — 키 재등록 필요."]
                return None, [f"공연시설: KOPIS 오류 ({rc} {msg})."]

            dbs = root.findall(".//db")
            if not dbs:
                break
            venues.extend(_parse_db(d) for d in dbs)
            if len(dbs) < _ROWS:
                break  # 마지막 페이지
            if cpage == max_pages:
                truncated = name_filter  # 상한 도달(이름필터 시 일부 누락 가능)

        # 시군구명 필터 (KOPIS 코드체계 미검증 → 이름 매칭)
        scope = "전국"
        if name_filter:
            venues = [v for v in venues
                      if sigungu in v["gugun"] and (not sido or sido[:2] in v["sido"])]
            scope = f"{sido} {sigungu}".strip()
            if truncated:
                notes.append(f"공연시설: 전국 {max_pages * _ROWS}건 상한 내 검색 — 일부 누락 가능(참고).")
        elif signgucode:
            scope = f"signgucode {signgucode}"

        if not venues:
            notes.append(f"공연시설: {scope} 데이터 없음.")
            return None, notes

        data = {"count": len(venues), "scope": scope, "venues": venues}
        notes.append(f"공연시설: {scope} {len(venues)}건 (KOPIS — 참고).")
        if cache:
            cache.set(cache_key, {"data": data, "notes": notes})
        return data, notes

    except ValueError as e:
        return None, [str(e)]
    except Exception as e:
        return None, [f"공연시설(KOPIS) 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()


def _int_or_none(v: Optional[str]) -> Optional[int]:
    if not v:
        return None
    try:
        return int(v.strip())
    except (ValueError, TypeError):
        return None
