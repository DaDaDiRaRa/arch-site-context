"""C2 총량제 엔진 테스트 — 실제 심의도서 수치로 검증 (CLAUDE.md §8.13).

값·판정을 동작구 본동·여의도 등 실측 심의도서와 대조한다.
공식 산수는 정확해야 하고, 법정면적 tier 는 세대규모별로 바르게 선택돼야 한다.
"""

from app.services import quota


def test_pick_tier_boundaries():
    tiers = [
        {"hh_min": 300, "hh_max": 500, "value": 1},
        {"hh_min": 500, "hh_max": 1000, "value": 2},
        {"hh_min": 1000, "hh_max": None, "value": 3},
    ]
    assert quota._pick_tier(tiers, 409)["value"] == 1
    assert quota._pick_tier(tiers, 500)["value"] == 2   # 하한 포함
    assert quota._pick_tier(tiers, 981)["value"] == 2
    assert quota._pick_tier(tiers, 2493)["value"] == 3  # 상한 없음
    assert quota._pick_tier(tiers, 100) is None         # 어느 tier 도 아님


def test_eval_legal_fixed_and_formula():
    # 고정값
    assert quota._eval_legal({"value": 158}, 800) == 158
    # 2000+ formula: 298+0.1*(hh-2000), 공공개방 ×1.2 → 여의도 도서관
    v = quota._eval_legal(
        {"formula": {"base": 298, "per_over": 0.1, "over": 2000}, "public_open_bonus": 1.2}, 2493
    )
    # (298 + 0.1*493)*1.2 = (298+49.3)*1.2 = 416.76
    assert abs(v - 416.76) < 0.5
    # 필수 아님 (value 없음)
    assert quota._eval_legal({"hh_min": 300, "hh_max": 500}, 400) is None


def test_library_shortage_matches_dongjak():
    """동작 본동 도서관: 산출면적 = (981+28829)×1.5×4%×2.5 − 1000.16 = 3471.34㎡, 부족."""
    rule = {
        "name": "작은도서관",
        "demand": {"type": "per_household_rate", "households": "new_plus_applied",
                   "params": {"multiplier": 1.5, "use_rate": 0.04, "area_per_person": 2.5}},
        "legal_min_tiers": [{"hh_min": 500, "hh_max": 1000, "value": 158, "confidence": "high"}],
    }
    f = quota.compute_facility(rule, new_hh=981, applied_hh=28829,
                               existing_area=1000.16, planned_area=515.92)
    assert abs(f.expected_people - 1788.6) < 0.1
    assert abs(f.required_area - 3471.34) < 0.1
    assert f.verdict == "부족시설"
    assert f.legal_min == 158
    assert f.plan_ok is True                      # 515.92 ≥ 158
    assert abs(f.plan_diff - 357.92) < 0.1


def test_gyeongrodang_sufficient_when_existing_exceeds():
    """경로당: 50 + 0.1×28829 − 3015.63 = -82.73 → 충족시설 (기존이 충분)."""
    rule = {
        "name": "경로당",
        "demand": {"type": "linear_household", "households": "applied",
                   "params": {"base": 50, "per_household": 0.1}},
        "legal_min_tiers": [{"hh_min": 500, "hh_max": 1000, "value": 330, "confidence": "high"}],
    }
    f = quota.compute_facility(rule, new_hh=981, applied_hh=28829, existing_area=3015.63)
    assert abs(f.required_area - (-82.73)) < 0.1
    assert f.verdict == "충족시설"


def test_childcare_needs_infant_else_confirm():
    """어린이집: 영유아/구세대 없으면 산정 불가 → '확인필요' (추정 안 함, 절대 원칙 3)."""
    rule = {
        "name": "어린이집",
        "demand": {"type": "infant_rate", "households": "new_plus_applied",
                   "params": {"attendance_rate": 0.8, "area_per_person": 6.6}},
        "legal_min_tiers": [{"hh_min": 500, "hh_max": 1000, "value": 330, "confidence": "high"}],
    }
    # 입력 있으면 산정
    f = quota.compute_facility(rule, new_hh=981, applied_hh=28829,
                               infant_pop=9652, gu_hh=188042, existing_area=5728.0)
    # 예상 = (9652/188042)×29810×0.8 ≈ 1224
    assert 1220 < f.expected_people < 1228
    assert f.verdict in ("부족시설", "충족시설")
    # 입력 없으면 확인필요
    f2 = quota.compute_facility(rule, new_hh=981, applied_hh=28829)
    assert f2.verdict == "확인필요"
    assert f2.required_area is None


def test_low_confidence_tier_flags_ordinance():
    """confidence=low tier 는 note 에 조례 확인 경고를 단다 (교정 핵심)."""
    rule = {
        "name": "작은도서관",
        "demand": {"type": "per_household_rate", "households": "new_plus_applied",
                   "params": {"multiplier": 1.5, "use_rate": 0.04, "area_per_person": 2.5}},
        "legal_min_tiers": [{"hh_min": 300, "hh_max": 500, "value": 108, "confidence": "low"}],
    }
    f = quota.compute_facility(rule, new_hh=409, applied_hh=45375)
    assert f.legal_min_confidence == "low"
    assert any("조례" in n for n in f.notes)


def test_library_not_required_under_500_real_config():
    """법령검증(#5): 작은도서관은 500세대 이상부터 의무 → 300~500세대 법정 None(필수 아님)."""
    cfg = quota.load_config()
    r = quota.compute_quota(new_hh=409, applied_hh=45375, cfg=cfg)  # 삼익 획지1 규모
    lib = next(f for f in r.facilities if f.name == "작은도서관")
    assert lib.legal_min is None                    # 필수 아님
    assert any("의무" in n or "필수 아님" in n for n in lib.notes)
    # 경로당은 300~500 에서도 의무(150세대~) → 법정 있음
    gr = next(f for f in r.facilities if f.name == "경로당")
    assert gr.legal_min == 198


def test_compute_quota_with_real_config():
    """실제 community_quota.json 로 여의도(2493세대, 2000+ tier) 전체 산정."""
    r = quota.compute_quota(
        new_hh=2493, applied_hh=14154, infant_pop=15753, gu_hh=192568,
        existing_area={"어린이집": 4575.0}, planned_area={"어린이집": 997.54},
        label="여의도시범",
    )
    assert r.new_households == 2493
    names = {f.name for f in r.facilities}
    assert "작은도서관" in names and "어린이집" in names
    # 2000+ tier 선택 → 도서관 법정 = (298+0.1*493)*1.2 ≈ 416.76
    lib = next(f for f in r.facilities if f.name == "작은도서관")
    assert lib.legal_min is not None and abs(lib.legal_min - 416.76) < 1.0
    # 총량 합계도 계산됨 (참고)
    assert r.total_quota_area is not None
