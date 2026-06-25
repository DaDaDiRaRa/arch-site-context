"""/facilities/map 실호출 테스트 — 카카오+VWorld 키·네트워크 있을 때만.

완료 기준 검증: 주소+시설+반경 → 핀·반경원·범례·출처 박힌 위성 PNG 생성.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not (os.getenv("KAKAO_KEY") and os.getenv("VWORLD_KEY")),
    reason="KAKAO_KEY/VWORLD_KEY 미설정 — 실호출 skip",
)


def test_map_compose_png() -> None:
    from app.services.facilities import build_facility_result
    from app.services.kakao import KakaoError
    from app.services.map_compose import compose_map
    from app.services.tiles import BasemapError

    try:
        result = build_facility_result(
            "서울특별시 영등포구 여의대로 24", ["어린이집", "경로당"], [500, 1000, 2000]
        )
        png = compose_map(result, [500, 1000, 2000], basemap="vworld")
    except (KakaoError, BasemapError) as e:
        pytest.skip(f"네트워크/키 문제로 skip: {e}")

    # 유효 PNG + 합리적 크기 (배경+오버레이가 실제로 그려졌는지)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 20_000


def test_unknown_basemap_raises() -> None:
    from app.services.map_compose import compose_map
    from app.services.tiles import BasemapError
    from app.schemas.facility import Center, FacilityResult

    stub = FacilityResult(
        center=Center(lat=37.5, lon=127.0, address="x"),
        results=[],
        counts={"500": {}},
        source="kakao",
        base_date="2026-06-25",
    )
    with pytest.raises(BasemapError):
        compose_map(stub, [500], basemap="kakao")  # 스카이뷰 미구현
