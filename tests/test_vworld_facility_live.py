"""VWorld 검색 보완 실호출 테스트 — 경로당 등 (키·네트워크 있을 때만).

§8.5 P1.5b: 카카오·OSM 가 누락하는 비상업시설(경로당)을 VWorld 검색으로 보완.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("VWORLD_KEY"),
    reason="VWORLD_KEY 미설정 — 실호출 skip",
)


def test_search_vworld_gyeongrodang() -> None:
    """경로당 검색 — category 필터로 오탐 제거된 결과."""
    from app.services import vworld

    res, notes = vworld.search_vworld(37.5260, 126.9244, 2000, ["경로당"])
    if not res:
        pytest.skip(f"결과 없음으로 skip: {notes}")

    # 전부 경로당 kind + 좌표 유효
    assert all(r["kind"] == "경로당" for r in res)
    assert all(33 < r["lat"] < 39 and 124 < r["lon"] < 132 for r in res)
    assert all(r["name"] for r in res)


def test_unmapped_kind_skipped() -> None:
    """매핑 없는 kind는 빈 결과 (조용히 생략)."""
    from app.services import vworld

    res, _ = vworld.search_vworld(37.5260, 126.9244, 1000, ["카페"])
    assert res == []


@pytest.mark.skipif(not os.getenv("KAKAO_KEY"), reason="KAKAO_KEY 미설정")
def test_facilities_vworld_complement() -> None:
    """build_facility_result 가 VWorld 보완을 병합 (경로당 src=vworld 포함)."""
    from app.services.facilities import build_facility_result
    from app.services.kakao import KakaoError

    try:
        r = build_facility_result(
            "서울특별시 영등포구 여의대로 24", ["경로당"], [500, 1000, 2000]
        )
    except KakaoError as e:
        pytest.skip(f"주소/네트워크 문제로 skip: {e}")

    # 경로당이 실제로 집계됐고, VWorld 가 source 에 반영됐는지
    if r.counts["2000"].get("경로당", 0) > 0:
        assert "vworld" in r.source or any(f.src == "vworld" for f in r.results)
