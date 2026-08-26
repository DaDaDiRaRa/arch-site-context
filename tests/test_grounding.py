"""수치 무결성 백스톱 순수 로직 (app/services/grounding.py) — 네트워크 0.

허용 풀의 정의는 "우리가 프롬프트로 보낸 텍스트에 등장한 숫자 전부". 스키마 값만 모으는
방식이 왜 안 되는지(항목명·자유서술 숫자)를 테스트로 못박는다.
"""

from __future__ import annotations

from app.services.grounding import allowed_pool, check_numbers


def test_pool_takes_every_number_in_prompt_text() -> None:
    prompt = (
        "- 1인가구비율: 38.2% (전국 33.4%) [DT_1JC1511 2024]\n"
        "- 총인구수: 29,281명\n"
        "- 어린이집: 7개"
    )
    pool = allowed_pool(prompt)
    for v in (1.0, 38.2, 33.4, 2024.0, 29281.0, 7.0):
        assert v in pool, v


def test_exact_and_rounded_values_pass() -> None:
    pool = allowed_pool("고령인구비율 19.2% / 총인구 29,281명")
    for answer in ("19.2%", "약 19%", "19.20%", "29,281명", "29281명"):
        _checked, unverified = check_numbers(answer, pool)
        assert unverified == [], answer


def test_item_name_digits_are_in_pool() -> None:
    """'1인가구비율' 의 1 — 값이 아니라 항목명이지만 모델에게 보여준 텍스트다."""
    pool = allowed_pool("- 1인가구비율: 38.2%")
    _checked, unverified = check_numbers("1인가구비율이 38.2%입니다", pool)
    assert unverified == []


def test_free_text_numbers_in_diagnosis_note_are_in_pool() -> None:
    """수급진단 note 의 자유서술 숫자도 프롬프트에 실려 나가므로 인용 가능하다."""
    pool = allowed_pool("- 보육시설 수급: 수요 낮음·공급 많음 — 반경 1000m 내 어린이집 23개")
    _checked, unverified = check_numbers("반경 1000m 내 어린이집 23개입니다", pool)
    assert unverified == []


def test_absent_number_is_flagged() -> None:
    pool = allowed_pool("고령인구비율 19.2%")
    checked, unverified = check_numbers("고령인구비율 19.2%, 노인복지시설 12개", pool)
    assert "12" in unverified and "19.2" in checked and "19.2" not in unverified


def test_derived_arithmetic_is_flagged() -> None:
    """차이(2.0%p)는 새 숫자 — 프롬프트가 금지하고 백스톱이 잡는다 (절대 원칙 2)."""
    pool = allowed_pool("고령인구비율 19.2% (전국 21.2%)")
    _checked, unverified = check_numbers("전국보다 2.0%p 낮습니다", pool)
    assert unverified == ["2.0"]


def test_unit_conversion_is_flagged() -> None:
    """1000m → '1km' 도 새 숫자 취급 — 단위 변환 금지(프롬프트 규칙 7)."""
    pool = allowed_pool("반경 2000m 내 어린이집 23개")
    _checked, unverified = check_numbers("반경 2km 내 23개입니다", pool)
    assert unverified == ["2"]


def test_duplicate_tokens_reported_once() -> None:
    pool = allowed_pool("고령인구비율 19.2%")
    checked, unverified = check_numbers("12개, 12개, 12개", pool)
    assert checked == ["12"] and unverified == ["12"]


def test_empty_pool_flags_everything() -> None:
    """데이터가 하나도 없으면 어떤 수치도 인용될 수 없다."""
    _checked, unverified = check_numbers("어린이집 7개입니다", allowed_pool(""))
    assert unverified == ["7"]


def test_no_numbers_is_verified() -> None:
    pool = allowed_pool("고령인구비율 19.2%")
    checked, unverified = check_numbers("제공된 통계는 시군구 평균값입니다.", pool)
    assert checked == [] and unverified == []


def test_identifier_digits_are_not_counted() -> None:
    """표ID 안의 숫자는 수량이 아니라 이름의 일부 — 풀에도, 검사 대상에도 넣지 않는다.

    실측에서 모델이 출처표ID(DT_1B04005N)를 인용하자 '검증한 수치 5개' 중 2개가 표ID
    조각이 돼 검증 개수가 거짓으로 부풀었다.
    """
    pool = allowed_pool("- 고령인구비율: 19.2% [DT_1B04005N 2025]")
    assert 4005.0 not in pool and 19.2 in pool and 2025.0 in pool

    checked, unverified = check_numbers("고령인구비율은 19.2%입니다 (DT_1B04005N 2025).", pool)
    assert checked == ["19.2", "2025"] and unverified == []


def test_unit_suffix_still_tokenized() -> None:
    """숫자 '뒤'에 붙은 글자는 단위·이름 접미라 정상 토큰 — 그래야 2km 변환을 잡는다."""
    pool = allowed_pool("반경 2000m 내 어린이집 23개 / 1인가구비율 45.1%")
    checked, unverified = check_numbers("반경 2km 내 23개, 1인가구 45.1%", pool)
    assert "2" in checked and unverified == ["2"]
