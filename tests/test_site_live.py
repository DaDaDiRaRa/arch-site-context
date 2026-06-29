"""/site 실호출 테스트 — VWorld 개별공시지가 (키·네트워크 있을 때만).

완료 기준 검증: 주소 → 좌표가 속한 필지의 개별공시지가(jiga) 실데이터.
data.go.kr 미승인 우회 — VWorld 연속지적도 LP_PA_CBND_BUBUN 사용.
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


def test_vworld_land_price() -> None:
    from app.services import vworld

    # 여의도 근처 좌표 (필지 위)
    lp, notes = vworld.fetch_land_price(126.9244, 37.5260)

    if lp is None:
        pytest.skip(f"VWorld 데이터 없음/오류로 skip: {notes}")

    assert lp["price_per_sqm"] > 0
    assert lp["year"] and lp["year"] >= 2020
    assert lp["pnu"]  # 필지고유번호
    assert notes and "개별공시지가" in notes[0]


@pytest.mark.skipif(
    not os.getenv("DATA_GO_KR_API_KEY"), reason="DATA_GO_KR_API_KEY 미설정 — 실호출 skip"
)
def test_molit_land_trade() -> None:
    """토지매매 실거래 — 작동 확인된 RTMS 엔드포인트 (data.go.kr)."""
    from app.services import molit

    trades, notes = molit.fetch_trades("토지매매", "11560", months=3, max_items=3)
    if not trades:
        pytest.skip(f"거래 없음/오류로 skip: {notes}")

    t = trades[0]
    assert t["category"] == "토지매매"
    assert t["deal_type"] == "매매"
    assert t["price_10k"] and t["price_10k"] > 0
    # 토지매매는 용도지역(landUse)이 note 로 들어옴
    assert "deal_ym" in t


@pytest.mark.skipif(
    not os.getenv("DATA_GO_KR_API_KEY"), reason="DATA_GO_KR_API_KEY 미설정 — 실호출 skip"
)
def test_molit_building_by_pnu() -> None:
    """건축HUB 건축물대장 — VWorld pnu(필지) 기준 조회."""
    from app.services import molit

    # 여의대로24 = 에프케이아이타워 필지
    b, notes = molit.fetch_building("1156011000100280001")
    if b is None:
        pytest.skip(f"대장 없음/오류로 skip: {notes}")

    assert b["purpose"]
    assert b["floors_above"] and b["floors_above"] > 0
    assert b["far"] and b["far"] > 0  # 용적률
    assert b["site_area_sqm"] and b["site_area_sqm"] > 0


def test_molit_building_bad_pnu() -> None:
    """PNU 없으면 graceful (추정 없이 건너뜀)."""
    from app.services import molit

    b, notes = molit.fetch_building("")
    assert b is None
    assert notes and "PNU" in notes[0]


def test_site_endpoint_land_price() -> None:
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.kakao import KakaoError

    client = TestClient(app)
    try:
        r = client.post("/site", json={"address": "서울특별시 영등포구 여의대로 24"})
    except KakaoError as e:
        pytest.skip(f"주소 해석 실패로 skip: {e}")

    assert r.status_code == 200
    body = r.json()
    lp = body["land_price"]
    assert lp["source"] == "VWorld_개별공시지가"
    # 공시지가가 실제로 채워졌는지 (VWorld 우회 동작 확인)
    if lp["price_per_sqm"] is not None:
        assert lp["price_per_sqm"] > 0
        assert lp["pnu"]
    else:
        # 빈값이면 notes 에 정직 표시 (no silent skip)
        assert any("공시지가" in n for n in body["notes"])
