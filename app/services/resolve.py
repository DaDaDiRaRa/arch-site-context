"""주소 해석 — 좌표 + 행정구역 코드 (P1.6).

카카오 주소검색(주: WGS84 좌표 + 법정동코드 b_code)을 우선 쓰고,
0건이면 JUSO(행안부)로 정규화·admCd를 얻은 뒤 카카오 키워드로 좌표를 보강한다.
둘 다 실패하면 추정하지 않고 멈춘다 (절대 원칙 1·3).

법정동코드(10자리) → 시군구코드(앞 5자리). KOSIS 통계는 시군구 평균이므로
모드 A의 region.code는 이 5자리를 쓴다 (절대 원칙 4).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional

import httpx

from app.services import juso, kakao

_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"


@dataclass
class ResolvedAddress:
    lat: float
    lon: float
    address: str  # 정규화된 주소 (가능하면 도로명)
    bcode: str = ""  # 법정동코드 10자리
    sgg_code: str = ""  # 시군구코드 5자리 (= bcode[:5])
    sido: str = ""
    sigungu: str = ""
    eupmyeondong: str = ""
    source: str = "kakao"  # kakao | kakao+juso | juso+kakao
    notes: list = field(default_factory=list)


def _sgg_from_bcode(bcode: str) -> str:
    """법정동코드 10자리 → 시군구코드 5자리."""
    return bcode[:5] if bcode and len(bcode) >= 5 else ""


def _kakao_address(address: str, client: httpx.Client) -> Optional[Dict]:
    """카카오 주소검색 첫 결과(좌표 + 법정동코드 + 행정구역명). 0건이면 None."""
    r = client.get(
        _ADDRESS_URL,
        params={"query": address},
        headers={"Authorization": f"KakaoAK {os.getenv('KAKAO_KEY', '')}"},
    )
    if r.status_code != 200:
        raise kakao.KakaoError(f"주소검색 실패 HTTP {r.status_code}: {r.text[:200]}")
    docs = r.json().get("documents", [])
    if not docs:
        return None
    d = docs[0]
    a = d.get("address") or {}
    return {
        "lat": float(d["y"]),
        "lon": float(d["x"]),
        "address": d.get("address_name", address),
        "bcode": a.get("b_code", ""),
        "sido": a.get("region_1depth_name", ""),
        "sigungu": a.get("region_2depth_name", ""),
        "eupmyeondong": a.get("region_3depth_name", ""),
    }


def resolve_address(
    address: str, client: Optional[httpx.Client] = None
) -> ResolvedAddress:
    """주소 → ResolvedAddress (좌표 + 행정구역 코드)."""
    own = client is None
    client = client or httpx.Client(timeout=10.0)
    notes: list = []
    try:
        # 1) 카카오 주소검색 (주 경로)
        k = _kakao_address(address, client)
        if k:
            res = ResolvedAddress(
                lat=k["lat"],
                lon=k["lon"],
                address=k["address"],
                bcode=k["bcode"],
                sgg_code=_sgg_from_bcode(k["bcode"]),
                sido=k["sido"],
                sigungu=k["sigungu"],
                eupmyeondong=k["eupmyeondong"],
                source="kakao",
                notes=notes,
            )
            # 법정동코드 누락 시 JUSO로 보강 (권위 코드)
            if not res.bcode:
                jj = juso.search_address(address, client=client)
                if jj and jj["adm_cd"]:
                    res.bcode = jj["adm_cd"]
                    res.sgg_code = _sgg_from_bcode(jj["adm_cd"])
                    res.source = "kakao+juso"
            return res

        # 2) 카카오 0건 → JUSO 정규화 후 좌표 보강
        jj = juso.search_address(address, client=client)
        if jj and jj["road_addr"]:
            notes.append("카카오 주소검색 0건 → JUSO 정규화 폴백.")
            coord = kakao.resolve_coord(jj["road_addr"], client=client)
            return ResolvedAddress(
                lat=coord["lat"],
                lon=coord["lon"],
                address=jj["road_addr"],
                bcode=jj["adm_cd"],
                sgg_code=_sgg_from_bcode(jj["adm_cd"]),
                sido=jj["sido"],
                sigungu=jj["sigungu"],
                eupmyeondong=jj["eupmyeondong"],
                source="juso+kakao",
                notes=notes,
            )

        # 3) 둘 다 실패 → 멈춘다
        raise kakao.KakaoError(f"주소를 해석할 수 없습니다 (카카오·JUSO 모두 0건): {address}")
    finally:
        if own:
            client.close()
