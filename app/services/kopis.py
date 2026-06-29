"""공연시설 — KOPIS 공연예술통합전산망 OpenAPI (KOPIS_KEY).

prfplc(공연시설 목록) → 시설명·지역·공연장수. XML 응답.
⚠️ 현재 키가 returncode 02(SERVICE KEY NOT REGISTERED)로 거부됨(2026-06-29) — 재등록 필요.
   골격은 완성, 키 활성화 시 바로 작동. 오류는 graceful (절대 원칙 3).
캐시 키: kopis:{signgucode}:{page}.
검증된 엔드포인트만 사용 (docs/API_VERIFICATION_2026-06-26).
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key

_URL = "http://www.kopis.or.kr/openApi/restful/prfplc"


def _key() -> str:
    k = os.getenv("KOPIS_KEY", "")
    if not k:
        raise ValueError("KOPIS_KEY 미설정")
    return k


def fetch_venues(
    signgucode: Optional[str] = None,
    rows: int = 30,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """공연시설 목록 (선택: KOPIS 시군구코드 필터).

    Returns:
        ({count, venues[{name, sido, gugun, id, hall_count}]}, notes) 또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    cache_key = make_key("kopis", signgucode or "ALL", str(rows))
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return cached.get("data"), cached.get("notes", [])

    params = {"service": key, "cpage": 1, "rows": rows}
    if signgucode:
        params["signgucode"] = signgucode

    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        r = client.get(_URL, params=params, timeout=15.0)
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
        venues = []
        for d in dbs:
            venues.append({
                "name": (d.findtext("fcltynm") or "").strip(),
                "sido": (d.findtext("sidonm") or "").strip(),
                "gugun": (d.findtext("gugunnm") or "").strip(),
                "id": (d.findtext("mt10id") or "").strip(),
                "hall_count": _int_or_none(d.findtext("mt13cnt")),
            })
        if not venues:
            return None, ["공연시설: 데이터 없음."]

        data = {"count": len(venues), "venues": venues}
        scope = f"시군구코드 {signgucode}" if signgucode else "전국"
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
