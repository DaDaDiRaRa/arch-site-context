"""POST /readout 실호출 테스트 — 키·네트워크 있을 때만 (공동주택 대지 readout).

기존 matrix 지표 + 크랙한 다차원 census 지표(사업체·빈집·신혼부부·장애인) + 파생.
각 지표 graceful — 일부 None 이어도 200 + notes (절대 원칙 3). 전국 작동(census 코드 자동해석).
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not (os.getenv("KAKAO_KEY") and os.getenv("KOSIS_KEY")),
    reason="KAKAO_KEY/KOSIS_KEY 미설정 — 실호출 skip",
)


def _post(address: str, project_type: str):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app).post(
        "/readout", json={"address": address, "project_type": project_type}
    )


def test_readout_redevelopment_seoul() -> None:
    """신반포2차(서초구) 재건축 — 인구·census·파생 다 채워지는지."""
    r = _post("서울 서초구 잠원동 60-3", "재건축")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["site"]["sgg_code"] == "11650"
    assert b["project_type"] == "재건축"

    # 시군구 평균 캐비엇 (절대 원칙 4)
    assert any("시군구 평균" in n for n in b["notes"])

    # 기존 matrix 지표 (인구·가구) 일부 존재
    items = {f["item"] for f in b["demographics"]}
    assert "고령인구비율" in items
    # 재건축 프리셋 강조 (고령·빈집·세대수·순이동)
    emphasized = {f["item"] for f in b["demographics"] if f["emphasized"]}
    assert "고령인구비율" in emphasized

    # 크랙한 census 지표 — 사업체수는 산업구조 breakdown 동반
    by_label = {c["label"]: c for c in b["context"]}
    assert "사업체수" in by_label
    if by_label["사업체수"]["value"] is not None:
        assert by_label["사업체수"]["value"] > 0
        assert len(by_label["사업체수"]["breakdown"]) > 0  # 산업대분류 구성


def test_readout_nonseoul_generalizes() -> None:
    """비서울(부산 수영구) census 코드 자동해석 — 사업체·빈집 실데이터."""
    r = _post("부산 수영구 남천동 23", "재개발")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["site"]["sigungu"] == "수영구"
    by_label = {c["label"]: c for c in b["context"]}
    # 적어도 사업체수 또는 빈집 중 하나는 실데이터 (전국 작동 증명)
    assert (by_label.get("사업체수", {}).get("value") or by_label.get("빈집", {}).get("value"))


def test_readout_private_greenfield_caveat() -> None:
    """민간 유형 → greenfield 캐비엇 note 발동."""
    r = _post("인천 서구 원당동", "민간")
    assert r.status_code == 200, r.text
    b = r.json()
    assert any("신규단지" in n for n in b["notes"])


def test_readout_bad_address_blocks() -> None:
    r = _post("존재하지않는주소zzz999", "재건축")
    assert r.status_code == 422
    assert r.json()["code"] == "ADDR_UNRESOLVED"
