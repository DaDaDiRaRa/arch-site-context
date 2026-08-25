"""종합 대지 읽기 HWP 보고서 마크다운 빌더 테스트 (§8.15) — app/deck/board_report_md.py.

네트워크 불필요 — board_slides.py(PPTX)와 같은 dict 입력을 순수 함수로 마크다운으로
조립하는 것만 검증한다. HWPX 변환(kordoc) 왕복은 test_kordoc_client.py 몫.
"""

from __future__ import annotations

from app.deck.board_report_md import build_board_report_md


def _board(**overrides):
    base = {"site": {"address": "서울 영등포구 여의대로 24"}, "base_date": "2026-07-09", "use_type": "주거"}
    base.update(overrides)
    return base


def test_minimal_board_still_renders_cover() -> None:
    md = build_board_report_md(_board())
    assert "# 종합 대지 읽기" in md
    assert "서울 영등포구 여의대로 24" in md
    assert md.endswith("최종 결정은 사람이 합니다.\n")


def test_empty_sections_are_skipped_silently() -> None:
    md = build_board_report_md(_board())
    for heading in ("## 커버리지", "## 동네 유형", "## 종합 해석", "## 설계 드라이버",
                     "## 교차시사점", "## 프로그램 함의", "## 수급 진단", "## 재해위험", "## 방법론"):
        assert heading not in md


def test_synthesis_wall_labels_both_blocks() -> None:
    md = build_board_report_md(_board(synthesis={
        "interpretation": "이 지역은 1인가구 비율이 전국 평균 대비 높다.",
        "judgment": "소형 평형이 유리할 수 있다고 가정한다.",
        "judgment_label": "AI 의견 — 검증/재현 보장 없음",
    }))
    assert "### ① 검증된 사실 (해석)" in md
    assert "### ② AI 판단 (의견) — AI 의견 — 검증/재현 보장 없음" in md
    itp_pos = md.index("① 검증된 사실")
    jdg_pos = md.index("② AI 판단")
    assert itp_pos < jdg_pos  # 사실이 먼저, 의견이 뒤 — 벽 순서


def test_indicators_table_includes_index_and_scope() -> None:
    md = build_board_report_md(_board(facts=[
        {"item": "1인가구비율", "value": 45.1, "national_avg": 33.4, "unit": "%",
         "index": 135, "index_band": "상회", "scope": "영등포구", "source_tbl": "DT_1JC1511"},
    ]))
    assert "## 인구·지역 지표 (전국=100 지수)" in md
    assert "| 1인가구비율 | 45.1% | 33.4% | 135 (상회) | 영등포구 | DT_1JC1511 |" in md


def test_table_cell_escapes_pipe_and_newline() -> None:
    md = build_board_report_md(_board(methodology={
        "summary": "요약", "sources": [{"name": "표 | 이름", "key": "K1", "publisher": "곳\n둘째줄", "note": ""}],
    }))
    assert "표 \\| 이름" in md
    assert "\n둘째줄" not in md  # 개행이 공백으로 치환돼 표 행이 안 깨짐


def test_diagnoses_table_renders_demand_and_supply() -> None:
    md = build_board_report_md(_board(diagnoses=[{
        "name": "보육시설 수급",
        "demand": {"item": "유소년인구비율", "value": 8.3, "unit": "%", "level": "낮음"},
        "supply": {"count": 12, "level": "보통"},
        "signal": "수요 낮음·공급 보통",
    }]))
    assert "보육시설 수급" in md
    assert "유소년인구비율 8.3% (낮음)" in md
    assert "12개 (보통)" in md


def test_hazards_section_reports_in_zone() -> None:
    md = build_board_report_md(_board(hazards={
        "flood": {"in_zone": True}, "landslide": {"in_zone": False},
        "heatwave": {"alert_count": 11, "warning_count": 31, "base_period": "2024~2025"},
    }))
    assert "홍수: 영향범위 포함" in md
    assert "산사태: 영향범위 밖" in md
    assert "경보 11건 · 주의보 31건 (2024~2025)" in md


# ── ★ §8.14 격리 — concept 은 board dict 에 주입돼 있을 때만 렌더 ─────────────


def test_concept_renders_only_when_injected() -> None:
    md_without = build_board_report_md(_board())
    assert "PROJECT DIRECTION" not in md_without

    md_with = build_board_report_md(_board(concept={
        "name": "RIVERFRONT", "tagline": "재생·연결",
        "keywords": [{"word": "방재", "gloss": "침수 대응", "basis": "홍수 드라이버"}],
        "label": "AI 제안 · 검증/재현 보장 없음",
    }))
    assert "PROJECT DIRECTION" in md_with
    assert "**RIVERFRONT** — 재생·연결" in md_with
    assert "근거: 홍수 드라이버" in md_with
