"""카카오 로컬 API 클라이언트 — 값을 실제로 호출해 가져온다 (절대 원칙 1).

- 주소 검색: 주소 → WGS84 좌표
- 키워드 검색: 중심좌표 + 반경 내 장소 (페이지네이션 끝까지)

키는 .env 의 KAKAO_KEY. 좌표는 전부 WGS84 (카카오 x=경도, y=위도).
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import httpx

from app.services.geo import split_rect
from app.services.http_retry import request_with_retry

_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
_COORD2REGION_URL = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"

# 카카오 키워드 검색은 페이지당 15건, 최대 45건(3페이지)까지 조회 가능.
_PAGE_SIZE = 15
_MAX_PAGE = 3
# 한 쿼리로 도달 가능한 최대 건수 (3페이지 × 15). 이걸 넘으면 영역 분할 필요.
_REACHABLE = _PAGE_SIZE * _MAX_PAGE
# 카카오 키워드 검색 radius 최대 20,000m
_MAX_RADIUS = 20_000
# 적응 분할 한계 — 깊이(셀 한 변이 약 1/2^depth로 줄어듦)와 총 호출 예산.
_MAX_DEPTH = 6
_CALL_BUDGET = 80


class KakaoError(RuntimeError):
    """카카오 API 호출 실패 (키 없음·HTTP 오류 등)."""


def _headers() -> Dict[str, str]:
    key = os.getenv("KAKAO_KEY")
    if not key:
        raise KakaoError("KAKAO_KEY 가 설정되지 않았습니다 (.env 확인).")
    return {"Authorization": f"KakaoAK {key}"}


def resolve_coord(address: str, client: Optional[httpx.Client] = None) -> Dict[str, float]:
    """주소 → WGS84 좌표 {lat, lon}. 결과 없으면 KakaoError.

    주소 검색이 0건이면 키워드 검색으로 1회 폴백 (지번/도로명 외 표기 대비).
    """
    own = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        r = request_with_retry(client, "GET", _ADDRESS_URL, params={"query": address}, headers=_headers())
        if r.status_code != 200:
            raise KakaoError(f"주소 검색 실패 HTTP {r.status_code}: {r.text[:200]}")
        docs = r.json().get("documents", [])

        if not docs:
            # 폴백: 키워드 검색 첫 결과 좌표
            rk = request_with_retry(
                client, "GET", _KEYWORD_URL, params={"query": address, "size": 1}, headers=_headers()
            )
            if rk.status_code == 200:
                docs = rk.json().get("documents", [])

        if not docs:
            raise KakaoError(f"주소를 좌표로 해석할 수 없습니다: {address}")

        d = docs[0]
        return {"lat": float(d["y"]), "lon": float(d["x"])}
    finally:
        if own:
            client.close()


def coord_to_hcode(
    lat: float, lon: float, client: Optional[httpx.Client] = None
) -> Optional[str]:
    """좌표 → 행정동코드(H, 10자리). 결과 없으면 None.

    coord2regioncode 는 법정동(B)·행정동(H) 둘 다 반환 — H(행정동)만 취한다.
    (서울 생활인구 ADSTRD_CODE_SE 8자리 = 이 H코드[:8].)
    """
    own = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        r = request_with_retry(
            client, "GET", _COORD2REGION_URL,
            params={"x": lon, "y": lat}, headers=_headers(),
        )
        if r.status_code != 200:
            return None
        for d in r.json().get("documents", []):
            if d.get("region_type") == "H" and d.get("code"):
                return d["code"]
        return None
    finally:
        if own:
            client.close()


def search_keyword(
    keyword: str,
    lat: float,
    lon: float,
    radius: int,
    client: Optional[httpx.Client] = None,
) -> List[Dict]:
    """중심좌표 + 반경 내 키워드 검색. 페이지네이션 끝까지 모아 원본 document 리스트 반환.

    반환 각 항목: {name, lat, lon} (카카오 x=경도→lon, y=위도→lat, WGS84).
    """
    own = client is None
    client = client or httpx.Client(timeout=10.0)
    radius = min(int(radius), _MAX_RADIUS)
    out: List[Dict] = []
    try:
        for page in range(1, _MAX_PAGE + 1):
            r = request_with_retry(
                client,
                "GET",
                _KEYWORD_URL,
                params={
                    "query": keyword,
                    "x": lon,  # 경도
                    "y": lat,  # 위도
                    "radius": radius,
                    "page": page,
                    "size": _PAGE_SIZE,
                    "sort": "distance",
                },
                headers=_headers(),
            )
            if r.status_code != 200:
                raise KakaoError(
                    f"키워드 검색 실패 HTTP {r.status_code}: {r.text[:200]}"
                )
            body = r.json()
            for d in body.get("documents", []):
                out.append(
                    {
                        "name": d.get("place_name", ""),
                        "lat": float(d["y"]),
                        "lon": float(d["x"]),
                    }
                )
            if body.get("meta", {}).get("is_end", True):
                break
        return out
    finally:
        if own:
            client.close()


def _keyword_rect_page(
    client: httpx.Client, keyword: str, rect: tuple, page: int
) -> Dict:
    """rect(사각형) 범위 키워드 검색 1페이지. 원본 JSON body 반환."""
    rect_str = ",".join(f"{c:.7f}" for c in rect)
    r = request_with_retry(
        client,
        "GET",
        _KEYWORD_URL,
        params={"query": keyword, "rect": rect_str, "page": page, "size": _PAGE_SIZE},
        headers=_headers(),
    )
    if r.status_code != 200:
        raise KakaoError(f"키워드(rect) 검색 실패 HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def _collect_rect(client: httpx.Client, keyword: str, rect: tuple) -> List[Dict]:
    """한 사각형 셀의 모든 페이지를 모아 document 리스트 반환."""
    out: List[Dict] = []
    for page in range(1, _MAX_PAGE + 1):
        body = _keyword_rect_page(client, keyword, rect, page)
        for d in body.get("documents", []):
            out.append(
                {"name": d.get("place_name", ""), "lat": float(d["y"]), "lon": float(d["x"])}
            )
        if body.get("meta", {}).get("is_end", True):
            break
    return out


def search_keyword_complete(
    keyword: str,
    bbox_rect: tuple,
    client: Optional[httpx.Client] = None,
) -> Dict:
    """45건 상한을 적응 분할로 회피하는 완전 검색.

    각 셀의 meta.total_count > 45 이면 4분할해 재귀. 깊이/호출예산 한계에 닿으면
    그 셀은 상한대로 받고 capped=True로 정직하게 표시 (no silent cap).

    반환: {"docs": [...], "capped": bool, "calls": int}
    """
    own = client is None
    client = client or httpx.Client(timeout=10.0)
    docs: List[Dict] = []
    capped = False
    calls = 0
    stack: List[tuple] = [(bbox_rect, 0)]
    try:
        while stack:
            rect, depth = stack.pop()
            if calls >= _CALL_BUDGET:
                capped = True
                break
            body = _keyword_rect_page(client, keyword, rect, 1)
            calls += 1
            meta = body.get("meta", {})
            total = meta.get("total_count", 0)
            if total == 0:
                continue

            if total > _REACHABLE and depth < _MAX_DEPTH:
                # 너무 빽빽 → 더 잘게 쪼갠다 (1페이지는 버리고 4분할 재수집)
                for sub in split_rect(rect):
                    stack.append((sub, depth + 1))
                continue

            # 도달 가능한 셀: 1페이지분 적재 후 나머지 페이지 보충
            for d in body.get("documents", []):
                docs.append(
                    {"name": d.get("place_name", ""), "lat": float(d["y"]), "lon": float(d["x"])}
                )
            if not meta.get("is_end", True):
                for page in range(2, _MAX_PAGE + 1):
                    b2 = _keyword_rect_page(client, keyword, rect, page)
                    calls += 1
                    for d in b2.get("documents", []):
                        docs.append(
                            {"name": d.get("place_name", ""), "lat": float(d["y"]), "lon": float(d["x"])}
                        )
                    if b2.get("meta", {}).get("is_end", True):
                        break
            if total > _REACHABLE and depth >= _MAX_DEPTH:
                # 최대 깊이에서도 빽빽 → 상한대로만 받음
                capped = True

        return {"docs": docs, "capped": capped, "calls": calls}
    finally:
        if own:
            client.close()
