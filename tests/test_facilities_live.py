"""실호출 통합테스트 — 카카오 키 + 네트워크가 있을 때만 실행.

KAKAO_KEY 없거나 네트워크 실패 시 skip (CI/오프라인 안전).
완료 기준 검증: 실제 주소로 어린이집·경로당 반경별 목록·개수가 나오는지.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("KAKAO_KEY"), reason="KAKAO_KEY 미설정 — 실호출 테스트 skip"
)


def test_facilities_real_address() -> None:
    from app.services.facilities import build_facility_result
    from app.services.kakao import KakaoError

    try:
        res = build_facility_result(
            "서울특별시 영등포구 여의대로 24",
            kinds=["어린이집", "경로당"],
            radii=[500, 1000, 2000],
        )
    except KakaoError as e:
        pytest.skip(f"네트워크/키 문제로 skip: {e}")

    # 좌표는 WGS84 (대한민국 범위)
    assert 33.0 <= res.center.lat <= 39.0
    assert 124.0 <= res.center.lon <= 132.0

    # 밴드 누적 단조성: 500 <= 1000 <= 2000
    for kind in ("어린이집", "경로당"):
        c500 = res.counts["500"][kind]
        c1000 = res.counts["1000"][kind]
        c2000 = res.counts["2000"][kind]
        assert c500 <= c1000 <= c2000

    # 목록의 dist_m 은 해당 밴드 이하, radius_band 정합
    for f in res.results:
        assert f.dist_m <= int(f.radius_band)
        assert 33.0 <= f.lat <= 39.0

    # counts 총합(2000) == 목록 내 kind별 개수
    for kind in ("어린이집", "경로당"):
        listed = sum(1 for f in res.results if f.kind == kind)
        assert res.counts["2000"][kind] == listed

    # 카카오 기반 + OSM·VWorld 보완 (경로당은 VWorld 가 보완 — §8.5)
    assert res.source.startswith("kakao")
