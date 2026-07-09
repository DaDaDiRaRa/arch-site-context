"""/board 실호출 테스트 (S3) — 키·네트워크 있을 때만.

기존 서비스(analyze·diagnose·site·seed)를 실제로 병렬 오케스트레이션해 한 객체로 합치는지,
그 위에서 S2 교차규칙이 도는지, coverage(도메인 확보 여부)가 채워지는지 end-to-end 확인.
graceful — 일부 도메인 실패해도 200 + notes.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.main import app

load_dotenv()

pytestmark = pytest.mark.skipif(
    not (os.getenv("KAKAO_KEY") and os.getenv("KOSIS_KEY")),
    reason="KAKAO_KEY/KOSIS_KEY 미설정 — 실호출 skip",
)

client = TestClient(app)


def test_board_live_end_to_end() -> None:
    r = client.post("/board", json={
        "address": "서울 영등포구 여의대로 24",
        "use_type": "주거", "radius": 1000, "resolution": "시군구",
    })
    assert r.status_code == 200, r.text
    b = r.json()

    # 공유 site + 기준일
    assert b["site"]["sgg_code"] == "11560"
    assert b["base_date"]

    # coverage 5개 도메인 — 확보/확인불가 무엇이든 항상 채워짐 (no silent skip)
    domains = {c["domain"] for c in b["coverage"]}
    assert domains == {"인구", "수급", "재해", "대지", "생활맥락"}

    # 최소한 인구는 실데이터로 확보 (KOSIS)
    assert b["facts"], f"facts 비어있음 — notes: {b['notes']}"

    # cross_implications 는 리스트(조건 미충족이면 빈 배열도 정상)
    assert isinstance(b["cross_implications"], list)
    for c in b["cross_implications"]:
        assert c["basis"] and c["domains"]  # 근거·도메인 없는 시사점은 없어야
