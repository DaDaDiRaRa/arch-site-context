"""상권(상가업소) 분포 — 소상공인시장진흥공단 상가(상권)정보 (DATA_GO_KR_API_KEY).

반경 내 상가업소 목록 → 업종 대분류별 점포 수 집계 (B553077 storeListInRadius).
※ SBIZ365(소상공인365) #29·#30(매출·폐업·창업·빈상가)은 REST API 가 없어(대시보드/파일만,
   §8.7) 대체 불가. 점포 '분포'는 이 실API(B553077)가 유일한 정식 경로 — §2 차별점 통과.
값 없음/오류는 graceful (절대 원칙 3). 캐시 키: sangwon:{lat}:{lon}:{radius}.
검증된 엔드포인트만 사용 (docs/API_VERIFICATION_2026-06-26).
"""

from __future__ import annotations

import os
from collections import Counter
from typing import List, Optional, Tuple

import httpx

from app.services.cache import Cache, make_key

_URL = "http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius"
_MAX_PAGES = 10  # 페이지당 1000건 → 최대 1만건


def _key() -> str:
    k = os.getenv("DATA_GO_KR_API_KEY", "")
    if not k:
        raise ValueError("DATA_GO_KR_API_KEY 미설정")
    return k


def fetch_store_district(
    lat: float,
    lon: float,
    radius: int = 500,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """반경 내 상가업소 분포 — 총 점포 수 + 업종 대분류별 집계.

    Returns:
        ({total, fetched, radius, by_large[(업종, 수)], stores[{name,lcls,mcls,scls,addr}]}, notes)
        또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    cache_key = make_key("sangwon", f"{lat:.5f}", f"{lon:.5f}", str(radius))
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return cached.get("data"), cached.get("notes", [])

    own = client is None
    client = client or httpx.Client(timeout=20.0)
    items: List[dict] = []
    total = 0
    try:
        page = 1
        while page <= _MAX_PAGES:
            r = client.get(
                _URL,
                params={"serviceKey": key, "radius": radius, "cx": lon, "cy": lat,
                        "type": "json", "numOfRows": 1000, "pageNo": page},
                timeout=20.0,
            )
            r.raise_for_status()
            body = r.json().get("body", {}) or {}
            total = int(body.get("totalCount") or total or 0)
            batch = body.get("items", []) or []
            items.extend(batch)
            if not batch or len(items) >= total:
                break
            page += 1

        if not items:
            return None, [f"상권: 반경 {radius}m 내 상가 데이터 없음."]

        by_large = Counter((i.get("indsLclsNm") or "미분류") for i in items)
        stores = [{
            "name": i.get("bizesNm"),
            "lcls": i.get("indsLclsNm"),
            "mcls": i.get("indsMclsNm"),
            "scls": i.get("indsSclsNm"),
            "addr": i.get("rdnmAdr") or i.get("lnoAdr"),
        } for i in items[:200]]

        data = {
            "total": total,
            "fetched": len(items),
            "radius": radius,
            "by_large": by_large.most_common(),
            "stores": stores,
        }
        capped = " (상한 도달 — 일부 누락 가능)" if len(items) < total else ""
        notes.append(f"상권: 반경 {radius}m 내 {total}개 상가, 업종 {len(by_large)}종{capped} "
                     f"(소상공인시장진흥공단 상가정보 — 참고).")
        if cache:
            cache.set(cache_key, {"data": data, "notes": notes})
        return data, notes

    except ValueError as e:
        return None, [str(e)]
    except Exception as e:
        return None, [f"상권 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()
