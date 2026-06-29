"""VWorld 데이터/검색 API — 개별공시지가 등.

VWORLD_KEY 사용 (WMTS 위성타일과 동일 키). data.go.kr 표준지/개별공시지가가
활용신청 미승인(403/500)이라, VWorld 연속지적도 레이어의 jiga(개별공시지가)로 우회한다.
개별공시지가는 필지별 값이라 표준지보다 대지 고유값에 가깝다 (절대 원칙 4).

호출 주의: 데이터 API(/req/data)는 domain 파라미터가 등록 도메인과 맞아야 한다.
누락/불일치 시 INCORRECT_KEY (키 문제 아님 — 도메인 매칭 문제). 미설정 시 기본 도메인 사용.
오류는 graceful 반환 — 추정 없이 None + notes (절대 원칙 1·3).
"""

from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Tuple

import httpx

from app.services.http_retry import request_with_retry

_DATA_URL = "https://api.vworld.kr/req/data"
_SEARCH_URL = "https://api.vworld.kr/req/search"
# 등록 도메인 (배포 서비스 URL). VWORLD_DOMAIN 으로 override 가능.
_DEFAULT_DOMAIN = "arch-site-context-30350777436.asia-northeast3.run.app"


def _key() -> str:
    k = os.getenv("VWORLD_KEY", "")
    if not k:
        raise ValueError("VWORLD_KEY 미설정")
    return k


def _domain() -> str:
    return os.getenv("VWORLD_DOMAIN") or _DEFAULT_DOMAIN


def fetch_land_price(
    lon: float,
    lat: float,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """좌표가 속한 필지의 개별공시지가 조회 (VWorld 연속지적도 LP_PA_CBND_BUBUN).

    Returns:
        ({price_per_sqm, year, pnu, addr, jibun}, notes) 또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        r = request_with_retry(
            client,
            "GET",
            _DATA_URL,
            params={
                "service": "data",
                "version": "2.0",
                "request": "GetFeature",
                "format": "json",
                "size": 1,
                "page": 1,
                "data": "LP_PA_CBND_BUBUN",
                "geomFilter": f"POINT({lon} {lat})",
                "key": key,
                "domain": _domain(),
            },
            timeout=12.0,
        )
        r.raise_for_status()
        body = r.json().get("response", {})
        status = body.get("status")
        if status != "OK":
            err = body.get("error", {}) or {}
            code = err.get("code", "")
            text = err.get("text", "")
            if code == "INCORRECT_KEY":
                return None, [f"개별공시지가: VWorld 도메인/키 불일치 ({_domain()}) — VWORLD_DOMAIN 확인."]
            return None, [f"개별공시지가: VWorld 응답 {status} {code} {text}".strip()]

        feats = (body.get("result", {}) or {}).get("featureCollection", {}).get("features", [])
        if not feats:
            return None, ["개별공시지가: 해당 좌표 필지 데이터 없음."]

        props = feats[0].get("properties", {}) or {}
        raw_price = (props.get("jiga") or "").strip()
        if not raw_price or raw_price == "0":
            return None, ["개별공시지가: 가격 정보 없음 (도로·국공유지 등일 수 있음)."]

        try:
            price = int(raw_price)
        except (ValueError, TypeError):
            return None, [f"개별공시지가: 가격 파싱 실패 ({raw_price})."]

        year = None
        gy = (props.get("gosi_year") or "").strip()
        if gy.isdigit():
            year = int(gy)

        result = {
            "price_per_sqm": price,
            "year": year,
            "pnu": (props.get("pnu") or "").strip(),
            "addr": (props.get("addr") or "").strip(),
            "jibun": (props.get("jibun") or "").strip(),
        }
        gm = (props.get("gosi_month") or "").strip()
        ym = f"{year}.{gm}" if year and gm else (str(year) if year else "")
        notes.append(f"개별공시지가: {ym} 기준 (VWorld, 해당 필지 값 — 참고).")
        return result, notes

    except ValueError as e:
        return None, [str(e)]
    except Exception as e:
        return None, [f"개별공시지가 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()


# ── 검색(POI) API — 카카오 누락 비상업시설 보완 (경로당 등) ────────────────────
# 한국어 시설명 → 검색질의 + category 필터 키워드.
# 키워드 검색은 오탐(주차장·협회 등)이 섞이므로 category 에 필터어가 든 것만 채택.
# 경로당은 카카오·OSM 모두 누락 빈번 (§8.5 P1.5b) — VWorld 가 가장 촘촘.
KIND_TO_VWORLD: Dict[str, str] = {
    "경로당": "경로당",
    "노인복지관": "노인복지관",
    "노인복지센터": "노인복지",
    "마을회관": "마을회관",
}
_SEARCH_SIZE = 100
_SEARCH_MAX_PAGES = 5  # 안전 상한 (= 최대 500건)


def search_vworld(
    lat: float,
    lon: float,
    radius_m: int,
    kinds: List[str],
    client: Optional[httpx.Client] = None,
) -> Tuple[List[dict], List[str]]:
    """VWorld 검색으로 비상업시설 보완. 결과: ([{name, lat, lon, kind}], notes).

    매핑 없는 kind는 조용히 생략. category 필터로 오탐 제거.
    오류 시 빈 리스트 — 호출자가 카카오/OSM 결과만 씀 (graceful, 절대 원칙 3).
    """
    results: List[dict] = []
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return [], [str(e)]

    domain = _domain()
    dlat = radius_m / 111_000.0
    dlon = radius_m / (111_000.0 * max(0.1, math.cos(math.radians(lat))))
    bbox = f"{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}"

    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        for kind in kinds:
            filt = KIND_TO_VWORLD.get(kind)
            if not filt:
                continue
            page = 1
            while page <= _SEARCH_MAX_PAGES:
                try:
                    r = request_with_retry(
                        client,
                        "GET",
                        _SEARCH_URL,
                        params={
                            "service": "search", "request": "search", "version": "2.0",
                            "crs": "EPSG:4326", "query": kind, "type": "place",
                            "format": "json", "size": _SEARCH_SIZE, "page": page,
                            "bbox": bbox, "key": key, "domain": domain,
                        },
                        timeout=12.0,
                    )
                    resp = r.json().get("response", {})
                except Exception:
                    break
                if resp.get("status") != "OK":
                    # NOT_FOUND(결과 0)는 정상 — 그 외만 표시
                    if resp.get("status") == "ERROR":
                        notes.append(f"VWorld 검색 '{kind}' 오류 (건너뜀).")
                    break
                items = (resp.get("result", {}) or {}).get("items", []) or []
                for it in items:
                    if filt not in (it.get("category") or ""):
                        continue
                    pt = it.get("point", {}) or {}
                    try:
                        ilon, ilat = float(pt["x"]), float(pt["y"])
                    except (KeyError, ValueError, TypeError):
                        continue
                    results.append({"name": it.get("title", "").strip(),
                                    "lat": ilat, "lon": ilon, "kind": kind})
                rec = resp.get("record", {}) or {}
                try:
                    total = int(rec.get("total", 0))
                except (ValueError, TypeError):
                    total = 0
                if page * _SEARCH_SIZE >= total:
                    break
                if page >= _SEARCH_MAX_PAGES and total > page * _SEARCH_SIZE:
                    notes.append(f"VWorld 검색 '{kind}': {total}건 중 {page * _SEARCH_SIZE}건만 (상한).")
                page += 1
    finally:
        if own:
            client.close()

    return results, notes
