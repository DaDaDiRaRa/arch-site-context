"""컨셉·설계방향 제안 테스트 (네트워크 불필요 — services/concept.py).

핵심 검증:
  - 근거(드라이버) 없으면 None (억지 창작 금지).
  - 키 없음 → 규칙 폴백: 드라이버 이름을 키워드로, 창작 네이밍(name) 없음, 라벨 항상 부착.
  - AI 출력 JSON 파싱·검증 (근거 없는/깨진 출력은 폴백).
  - ★ 격리: BoardResult/board_brief 스키마에 concept 필드가 없다 (계약 밖).
"""

from __future__ import annotations

from app.schemas.design_drivers import DesignDriver, DriverEvidence
from app.services import concept
from app.services.concept import CONCEPT_LABEL, _parse, _rule_concept, derive_concept


def _drivers():
    return [
        DesignDriver(rank=1, name="방재·저층부 대응", response="저지대 침수 대응 저층부·전기실 상부",
                     strength=4.0, evidence=[DriverEvidence(key="홍수", detail="영향범위 포함", proximity="읍면동")]),
        DesignDriver(rank=2, name="접근성·무장애", response="무장애 동선·근린 의료 접근",
                     strength=3.6, evidence=[DriverEvidence(key="고령인구비율", detail="22.1% (지수 113)", proximity="시군구")]),
    ]


# ── 근거 없으면 None (억지 창작 금지) ────────────────────────────────────────
def test_no_evidence_returns_none(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert derive_concept("주거", facts=[], drivers=[]) is None


# ── 키 없음 → 규칙 폴백 (드라이버 이름 = 키워드, 창작명 없음, 라벨 부착) ──────
def test_rule_fallback_uses_driver_names(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    con = derive_concept("주거", facts=[], drivers=_drivers())
    assert con is not None
    assert con["source"] == "rule_based_fallback"
    assert con["name"] == ""  # 규칙 폴백은 창작 네이밍 안 만듦 (정직)
    words = [k["word"] for k in con["keywords"]]
    assert "방재·저층부 대응" in words
    # 각 키워드에 근거가 실린다
    assert any("홍수" in k["basis"] for k in con["keywords"])
    assert con["label"] == CONCEPT_LABEL


def test_rule_concept_none_without_named_drivers() -> None:
    # 이름 없는 드라이버만 있으면 키워드가 안 생겨 None
    assert _rule_concept([], None) is None


# ── AI 출력 파싱 ─────────────────────────────────────────────────────────────
def test_parse_valid_json() -> None:
    text = (
        '설명 머리말...\n{"name": "TRANSIT", "tagline": "재생·연결",'
        ' "keywords": [{"word": "방재", "gloss": "침수 대응", "basis": "홍수 드라이버"}]}'
    )
    p = _parse(text)
    assert p is not None
    assert p["name"] == "TRANSIT"
    assert p["keywords"][0]["word"] == "방재"


def test_parse_rejects_broken_or_empty() -> None:
    assert _parse(None) is None
    assert _parse("컨셉을 만들 수 없습니다") is None  # JSON 없음
    assert _parse('{"name": "X", "keywords": []}') is None  # 키워드 없음


# ── AI 경로: 모델 호출을 monkeypatch 로 대체 (네트워크 0) ─────────────────────
def test_ai_path_attaches_label_and_source(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        concept.synthesis, "_call",
        lambda *a, **k: '{"name": "RIVERFRONT", "tagline": "", '
        '"keywords": [{"word": "방재", "gloss": "침수 대응", "basis": "홍수 영향범위"}]}',
    )
    con = derive_concept("주거", facts=[], drivers=_drivers())
    assert con["source"] == "ai"
    assert con["model"] == concept._MODEL
    assert con["name"] == "RIVERFRONT"
    assert con["label"] == CONCEPT_LABEL  # 코드가 항상 부착


def test_ai_parse_failure_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(concept.synthesis, "_call", lambda *a, **k: "이상한 출력 no json")
    con = derive_concept("주거", facts=[], drivers=_drivers())
    assert con["source"] == "rule_based_fallback"


# ── ★ 격리: concept 는 계약(BoardResult/board_brief)에 없다 ───────────────────
def test_concept_is_not_in_board_contract() -> None:
    from app.schemas.board import BoardResult
    assert "concept" not in BoardResult.model_fields
