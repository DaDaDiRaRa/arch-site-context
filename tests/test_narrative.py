"""한 문단 서술 테스트 (P6).

규칙 폴백은 네트워크 불필요 — 완료 기준 '둘 다 facts 보존' 핵심을 검증.
AI 경로는 ANTHROPIC_API_KEY 있을 때만.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from app.services.narrative import _rule_based, compose_narrative

load_dotenv()

_FACTS = [
    {"item": "고령인구비율", "value": 19.2, "national_avg": 21.2, "unit": "%", "source_tbl": "DT_1B04005N", "year": 2025},
    {"item": "노년부양비", "value": 26.5, "national_avg": 31.0, "unit": "%", "source_tbl": "DT_1B04005N", "year": 2025},
]
_IMPS = [{"text": "무장애 동선·휴게공간 검토", "basis": "고령인구비율", "tag": "참고"}]


def _preserves_facts(paragraph: str) -> bool:
    # facts 의 핵심 수치가 문단에 보존되는지 (값 인용 확인)
    return "19.2" in paragraph and "26.5" in paragraph


# ── 규칙 폴백 (네트워크 불필요) ──────────────────────────────
def test_rule_based_mentions_region_year_and_facts() -> None:
    p = _rule_based("영등포구", 2025, "의료", _FACTS, _IMPS)
    assert "영등포구 기준" in p
    assert "2025" in p
    assert _preserves_facts(p)
    assert "시군구 평균" in p  # 대지 고유값 아님 표기


def test_fallback_when_no_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    text, source, _notes = compose_narrative("영등포구", 2025, "의료", _FACTS, _IMPS)
    assert source == "rule_based_fallback"
    assert _preserves_facts(text)  # 폴백이어도 facts 보존


def test_fallback_empty_facts(monkeypatch) -> None:
    # facts 없으면 라우터가 ErrorBlock 처리하지만, 서술 자체는 안전해야 함.
    # 규칙 폴백 경로를 검증하므로 AI 키를 지워 비결정적 AI 호출을 배제 (결정적 테스트).
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    text, source, _notes = compose_narrative("영등포구", 2025, "주거", [], [])
    assert source == "rule_based_fallback"
    assert "영등포구 기준" in text


# ── AI 경로 (키 있을 때만) ───────────────────────────────────
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY 미설정")
def test_ai_path_preserves_facts() -> None:
    text, source, _notes = compose_narrative("영등포구", 2025, "의료", _FACTS, _IMPS)
    # 정상이면 ai, 일시 실패면 폴백 — 둘 다 facts 보존이 핵심
    assert source in ("ai", "rule_based_fallback")
    assert _preserves_facts(text)
    assert "영등포" in text


# ── 수치 무결성 백스톱 (services/grounding.py) — AI 문단이 facts 밖 숫자를 쓰면 규칙 폴백 ──
# `/ask` 와 달리 교정 재요청을 하지 않는다: 여기엔 코드가 만든(정의상 그라운디드) 규칙
# 문단이 이미 있어 공짜로 안전한 대안이 있기 때문. 대체 사실은 notes 로 올린다(원칙 3).

import sys
import types


def _fake_anthropic(monkeypatch, text):
    class _Msgs:
        def create(self, **k):
            blk = types.SimpleNamespace(type="text", text=text)
            return types.SimpleNamespace(stop_reason="end_turn", content=[blk])

    class _Client:
        def with_options(self, **k):
            return self
        messages = _Msgs()

    fake = types.ModuleType("anthropic")
    fake.Anthropic = lambda *a, **k: _Client()
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def test_grounded_ai_paragraph_is_kept(monkeypatch) -> None:
    _fake_anthropic(monkeypatch, "영등포구의 고령인구비율은 19.2%, 노년부양비는 26.5%입니다(2025).")
    text, source, notes = compose_narrative("영등포구", 2025, "의료", _FACTS, _IMPS)
    assert source == "ai" and notes == [] and "19.2" in text


def test_ungrounded_number_falls_back_to_rules(monkeypatch) -> None:
    """facts 에 없는 33.7 이 섞이면 AI 문단을 버리고 규칙 문단으로."""
    _fake_anthropic(monkeypatch, "고령인구비율은 19.2%이고 1인가구비율은 33.7%입니다.")
    text, source, notes = compose_narrative("영등포구", 2025, "의료", _FACTS, _IMPS)

    assert source == "rule_based_fallback"
    assert notes and "33.7" in notes[0] and "수치 무결성" in notes[0]
    assert "33.7" not in text          # 환각 숫자가 사용자에게 안 나간다
    assert _preserves_facts(text)      # 규칙 폴백은 facts 를 그대로 보존
