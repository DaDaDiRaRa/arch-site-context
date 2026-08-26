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
    """text 는 str 또는 list[str] — list 면 호출 순서대로 준다(교정 재시도 검증용)."""
    texts = [text] if isinstance(text, str) else list(text)
    calls = {"n": 0}

    class _Msgs:
        def create(self, **k):
            i = min(calls["n"], len(texts) - 1)
            calls["n"] += 1
            blk = types.SimpleNamespace(type="text", text=texts[i])
            return types.SimpleNamespace(stop_reason=stop_reason, content=[blk])

    class _Client:
        def with_options(self, **k):
            return self
        messages = _Msgs()

    fake = types.ModuleType("anthropic")
    fake.Anthropic = lambda *a, **k: _Client()
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return calls


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
    answer, answerable, source, _, _gr = ask.answer_grounded(_BUNDLE, "고령인구 비율은?")
    assert answerable is True and source == "ai"
    assert "19.2" in answer


def test_grounded_blocks_when_out_of_data(monkeypatch) -> None:
    # 모델이 '확인 불가'로 시작 → 데이터 밖 (추정 안 함)
    _install_fake_anthropic(monkeypatch, "확인 불가: 제공된 데이터에 해당 정보가 없습니다.")
    answer, answerable, source, _, _gr = ask.answer_grounded(_BUNDLE, "이 동네 집값 전망은?")
    assert answerable is False and source == "no_data"


def test_grounded_no_api_key_is_honest(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    answer, answerable, source, _, _gr = ask.answer_grounded(_BUNDLE, "고령인구?")
    assert source == "ai_unavailable" and answerable is False
    assert "ANTHROPIC_API_KEY" in answer  # 환각 대신 정직한 안내


def test_build_answer_includes_bundle(monkeypatch) -> None:
    # gather_bundle·answer_grounded 모킹 → 결과에 근거 번들이 동봉되는지
    monkeypatch.setattr(ask.compare, "gather_bundle", lambda *a, **k: _BUNDLE)
    monkeypatch.setattr(ask, "answer_grounded", lambda b, q: ("답.", True, "ai", [], None))
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


# ── 수치 무결성 백스톱 (services/grounding.py) ──────────────────────────────
# 그라운딩이 프롬프트 규칙에만 의존하던 구멍을 코드로 막은 것. 정책 = A+C:
# 위반 수치를 짚어 1회 교정 재요청 → 그래도 남으면 답변을 버리고 '확인 불가'(절대 원칙 3).

_BUNDLE_1IN = {
    **_BUNDLE,
    "facts": [
        {"item": "1인가구비율", "value": 38.2, "national_avg": 33.4, "unit": "%",
         "source_tbl": "DT_1JC1511", "year": 2024},
    ],
}


def test_rounding_is_allowed(monkeypatch) -> None:
    """'약 19%'(← 19.2)는 새 숫자가 아니라 같은 값의 표현 — 차단하면 안 된다."""
    _install_fake_anthropic(monkeypatch, "영등포구 기준 고령인구비율은 약 19%입니다 (참고).")
    _a, answerable, source, _n, gr = ask.answer_grounded(_BUNDLE, "고령인구 비율은?")
    assert answerable is True and source == "ai"
    assert gr.verified is True and gr.unverified == [] and gr.retried is False


def test_item_name_digits_do_not_false_positive(monkeypatch) -> None:
    """항목명에 박힌 숫자(1인가구비율)도 '보여준 텍스트'라 통과해야 한다."""
    _install_fake_anthropic(monkeypatch, "1인가구비율은 38.2%로 전국 33.4%보다 높습니다.")
    _a, answerable, _s, _n, gr = ask.answer_grounded(_BUNDLE_1IN, "1인가구는?")
    assert answerable is True and gr.verified is True
    assert "1" in gr.checked and "38.2" in gr.checked


def test_hallucinated_number_blocked_after_retry(monkeypatch) -> None:
    """데이터에 없는 수치가 재요청 후에도 남으면 답변을 버리고 멈춘다."""
    bad = "영등포구 고령인구비율은 19.2%이고 노인복지시설은 12개입니다."  # 12 = 없는 값
    calls = _install_fake_anthropic(monkeypatch, [bad, bad])
    answer, answerable, source, notes, gr = ask.answer_grounded(_BUNDLE, "노인복지시설 몇 개야?")
    assert calls["n"] == 2                      # 1차 + 교정 재요청 1회
    assert answerable is False and source == "no_data"
    assert gr.verified is False and gr.retried is True and "12" in gr.unverified
    assert answer.startswith("확인 불가") and "12" in answer
    assert notes and "차단" in notes[0]
    assert "노인복지시설은 12개" not in answer   # 환각 문장 자체가 노출되지 않는다


def test_retry_converges_to_verified_answer(monkeypatch) -> None:
    """교정 재요청으로 수렴하면 정상 답변으로 살린다(숫자 하나 때문에 통째로 날리지 않음)."""
    calls = _install_fake_anthropic(monkeypatch, [
        "고령인구비율 19.2%, 노인복지시설 12개입니다.",   # 12 위반
        "고령인구비율은 19.2%입니다. 어린이집은 7개입니다.",
    ])
    answer, answerable, source, _n, gr = ask.answer_grounded(_BUNDLE, "고령인구?")
    assert calls["n"] == 2
    assert answerable is True and source == "ai"
    assert gr.verified is True and gr.retried is True
    assert "7" in answer


def test_no_data_answer_is_not_double_blocked(monkeypatch) -> None:
    """이미 '확인 불가'로 멈춘 답은 사유 문장 속 숫자로 이중 차단하지 않는다."""
    calls = _install_fake_anthropic(monkeypatch, "확인 불가: 2020년 자료가 제공되지 않았습니다.")
    answer, answerable, source, _n, gr = ask.answer_grounded(_BUNDLE, "2020년은?")
    assert calls["n"] == 1 and answerable is False and source == "no_data"
    assert gr is None and answer.startswith("확인 불가")


def test_retry_message_numbers_do_not_enter_pool(monkeypatch) -> None:
    """교정 메시지엔 위반 수치가 적힌다 — 그걸 풀에 넣으면 환각이 통과해버린다."""
    bad = "노인복지시설은 12개입니다."
    _install_fake_anthropic(monkeypatch, [bad, bad])
    _a, answerable, _s, _n, gr = ask.answer_grounded(_BUNDLE, "노인복지시설?")
    assert answerable is False and "12" in gr.unverified
