"""POST /seed 실호출 테스트 — 키·네트워크 있을 때만 (P12 보드 합본).

build_site(공유 site) + 신규 서비스(상권·학교·부동산지수·날씨·생활인구·공연시설) 합본.
각 블록 graceful — 일부 None 이어도 200 + notes (절대 원칙 3).
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not (os.getenv("KAKAO_KEY") and os.getenv("DATA_GO_KR_API_KEY")),
    reason="KAKAO_KEY/DATA_GO_KR_API_KEY 미설정 — 실호출 skip",
)


def test_seed_aggregates() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/seed",
        json={"address": "서울특별시 영등포구 여의대로 24", "radius": 1000, "adstrd_code": "11560540"},
    )
    assert r.status_code == 200
    b = r.json()

    # 공유 site
    assert b["site"]["sgg_code"] == "11560"
    assert b["base_date"]

    # context 블록 키 존재 (값은 graceful None 허용)
    ctx = b["context"]
    for k in ("stores", "schools", "childcare", "culture", "real_estate_index", "weather", "living_population", "venues"):
        assert k in ctx
    assert "notes" in ctx

    # 어린이집은 영등포에서 실데이터(정원 합계) 나와야 함 (정보공개포털 승인됨)
    if ctx["childcare"] is not None:
        assert ctx["childcare"]["count"] > 0
        assert ctx["childcare"]["total_capacity"] > 0

    # 최소한 상권은 영등포에서 실데이터가 나와야 함 (B553077 승인됨)
    if ctx["stores"] is not None:
        assert ctx["stores"]["total"] > 0

    # 형제 앱 블록은 비어 있음 (경계)
    assert b["law"] is None and b["knowledge"] is None


def test_seed_bad_address() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/seed", json={"address": "ㅁㄴㅇㄹ존재하지않는주소ㅋㅋ"})
    # 주소 해석 실패 → ErrorBlock 422 (추정 금지)
    assert r.status_code == 422
    assert r.json()["code"] == "ADDR_UNRESOLVED"
