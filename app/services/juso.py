"""행안부 도로명주소 Open API 클라이언트 (juso.go.kr).

용도: 주소 정규화 + 법정동코드(admCd) 권위 확인. 카카오 주소검색 실패 시 폴백.
좌표는 주지 않으므로(좌표제공 API 별도), 좌표는 카카오가 담당한다.

키: .env 의 JUSO_API_KEY. 현재 'dev' 키는 개발서버(business.juso.go.kr) 전용 —
운영 배포(P8) 시 운영키 필요.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

import httpx

from app.services.http_retry import request_with_retry

_ADDR_URL = "https://business.juso.go.kr/addrlink/addrLinkApi.do"


class JusoError(RuntimeError):
    """JUSO API 호출 실패."""


def _key() -> str:
    key = os.getenv("JUSO_API_KEY")
    if not key:
        raise JusoError("JUSO_API_KEY 가 설정되지 않았습니다 (.env 확인).")
    return key


def search_address(
    query: str, client: Optional[httpx.Client] = None
) -> Optional[Dict[str, str]]:
    """주소 1건 검색. 결과 없으면 None.

    반환: {road_addr, jibun_addr, adm_cd(법정동코드 10자리), sido, sigungu, eupmyeondong, zip}
    """
    own = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        r = request_with_retry(
            client,
            "GET",
            _ADDR_URL,
            params={
                "confmKey": _key(),
                "currentPage": 1,
                "countPerPage": 1,
                "keyword": query,
                "resultType": "json",
            },
        )
        if r.status_code != 200:
            raise JusoError(f"주소검색 실패 HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        common = data.get("results", {}).get("common", {})
        if common.get("errorCode") not in ("0", 0):
            raise JusoError(
                f"JUSO 오류 {common.get('errorCode')}: {common.get('errorMessage')}"
            )
        juso_list = data.get("results", {}).get("juso", []) or []
        if not juso_list:
            return None
        j = juso_list[0]
        return {
            "road_addr": j.get("roadAddr", ""),
            "jibun_addr": j.get("jibunAddr", ""),
            "adm_cd": j.get("admCd", ""),  # 법정동코드 10자리
            "sido": j.get("siNm", ""),
            "sigungu": j.get("sggNm", ""),
            "eupmyeondong": j.get("emdNm", ""),
            "zip": j.get("zipNo", ""),
        }
    finally:
        if own:
            client.close()
