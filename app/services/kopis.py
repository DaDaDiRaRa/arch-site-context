"""공연시설 — KOPIS 공연예술통합전산망 OpenAPI (KOPIS_KEY).

prfplc(공연시설 목록) → 시설명·지역·공연장수. XML 응답.

★시군구 매핑 (2026-06-29 실API 검증): **KOPIS signgucode = 행안부 시군구코드 앞 4자리**.
  영등포 11560→1156(61건 전부 영등포), 관악 11620→1162, 부산해운대 26350→2635,
  성남분당 41135→4113 모두 server-side 정확 필터. → site.sgg_code[:4] 그대로 사용.
  이름필터(sidonm/gugunnm)는 코드 없을 때만 쓰는 폴백 (전국 페이징·1000건 상한·누락 가능).
  rows 최대 100 (초과 시 returncode 06).
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
_ROWS = 100  # KOPIS rows 상한 (초과 시 returncode 06)
_MAX_PAGES = 10  # 페이징 상한 (이름필터=전국 1000건, signgucode=시군구당 1000건 — 충분)


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
    """공연시설 목록.

    signgucode 지정 시(권장): KOPIS 서버측 정확 필터(= 행안부 sgg_code[:4], 2026-06-29 검증).
        페이징하되 시군구 단위라 보통 1페이지(<100건)면 충분 — 상한·누락 없음.
    signgucode 없고 sigungu 만 있으면: 전국 페이징(상한 _MAX_PAGES) 후 gugunnm 이름필터(폴백).
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

    # signgucode(서버필터)·이름필터 둘 다 페이징. 코드 없고 이름도 없으면 1페이지(전국 표본).
    name_filter = bool(sigungu) and not signgucode
    max_pages = _MAX_PAGES if (name_filter or signgucode) else 1

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
                truncated = name_filter  # 이름필터만 전국 상한 도달 시 누락 가능

        # scope 라벨 + (이름필터일 때만) 후처리 필터. signgucode 는 서버에서 이미 정확 필터됨.
        scope = "전국"
        if signgucode:
            scope = f"{sido} {sigungu}".strip() or f"signgucode {signgucode}"
        elif name_filter:
            venues = [v for v in venues
                      if sigungu in v["gugun"] and (not sido or sido[:2] in v["sido"])]
            scope = f"{sido} {sigungu}".strip()
            if truncated:
                notes.append(f"공연시설: 전국 {max_pages * _ROWS}건 상한 내 검색 — 일부 누락 가능(참고).")

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
