"""P10 물어보기 테스트.

그라운딩 핵심을 결정적으로 검증: 답이 '확인 불가'로 시작하면 answerable=False,
정상 답이면 True, 키 없으면 ai_unavailable(환각 안 함). anthropic SDK 는 가짜 모듈로 주입.
라이브는 키 있을 때만.
"""

from __future__ import annotations

import os
import sys
import types

import pytest
from dotenv import load_dotenv

from app.schemas.region import Region
from app.services import ask

load_dotenv()


# ── 가짜 anthropic SDK 주입 ──────────────────────────────────────────────
def _install_fake_anthropic(monkeypatch, text, stop_reason="end_turn"):
    blk = types.SimpleNamespace(type="text", text=text)
    resp = types.SimpleNamespace(stop_reason=stop_reason, content=[blk])

    class _Msgs:
        def create(self, **k):
            return resp

    class _Client:
        def with_options(self, **k):
            return self
        messages = _Msgs()

    fake = types.ModuleType("anthropic")
    fake.Anthropic = lambda *a, **k: _Client()
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


_BUNDLE = {
    "region": Region(name="영등포구", code="11560", resolution="시군구"),
    "facts": [{"item": "고령인구비율", "value": 19.2, "national_avg": 21.2, "unit": "%",
               "source_tbl": "DT_1B04005N", "year": 2025}],
    "counts": {"어린이집": 7},
    "diagnoses": [],
    "notes": [],
}


def test_grounded_answerable_when_data_present(monkeypatch) -> None:
    _install_fake_anthropic(monkeypatch, "영등포구 기준 고령인구비율은 19.2%로 전국(21.2%)보다 낮습니다.")
    answer, answerable, source, _ = ask.answer_grounded(_BUNDLE, "고령인구 비율은?")
    assert answerable is True and source == "ai"
    assert "19.2" in answer


def test_grounded_blocks_when_out_of_data(monkeypatch) -> None:
    # 모델이 '확인 불가'로 시작 → 데이터 밖 (추정 안 함)
    _install_fake_anthropic(monkeypatch, "확인 불가: 제공된 데이터에 해당 정보가 없습니다.")
    answer, answerable, source, _ = ask.answer_grounded(_BUNDLE, "이 동네 집값 전망은?")
    assert answerable is False and source == "no_data"


def test_grounded_no_api_key_is_honest(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    answer, answerable, source, _ = ask.answer_grounded(_BUNDLE, "고령인구?")
    assert source == "ai_unavailable" and answerable is False
    assert "ANTHROPIC_API_KEY" in answer  # 환각 대신 정직한 안내


def test_build_answer_includes_bundle(monkeypatch) -> None:
    # gather_bundle·answer_grounded 모킹 → 결과에 근거 번들이 동봉되는지
    monkeypatch.setattr(ask.compare, "gather_bundle", lambda *a, **k: _BUNDLE)
    monkeypatch.setattr(ask, "answer_grounded", lambda b, q: ("답.", True, "ai", []))
    from app.schemas.ask import AskRequest

    res = ask.build_answer(AskRequest(address="서울 영등포구 여의대로 24", question="고령인구?"))
    assert res.answerable and res.source == "ai"
    assert res.region.name == "영등포구"
    assert any(f.item == "고령인구비율" for f in res.facts)  # 투명성: 근거 노출
    assert res.counts == {"어린이집": 7}


def test_ask_endpoint_empty_question() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/ask", json={"address": "서울 영등포구 여의대로 24", "question": "  "})
    assert r.status_code == 422
    assert r.json()["code"] == "EMPTY_QUESTION"


# ── 라이브 (키 있을 때만) ────────────────────────────────────────────────
@pytest.mark.skipif(
    not (os.getenv("KOSIS_KEY") and os.getenv("KAKAO_KEY") and os.getenv("ANTHROPIC_API_KEY")),
    reason="키 미설정 — 실호출 skip",
)
def test_ask_endpoint_real_grounded() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/ask", json={
        "address": "서울 영등포구 여의대로 24",
        "question": "고령인구 비율이 전국보다 높아 낮아?",
        "use_type": "주거",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["region"]["code"] == "11560"
    assert len(body["facts"]) >= 1  # 근거 데이터 동봉
    assert body["source"] in ("ai", "no_data")
