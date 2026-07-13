"""심의 현황팩 오케스트레이터 테스트 — C1→C2 글루 (CLAUDE.md §8.13).

survey(걸침)·구통계 조회를 monkeypatch 하고, 걸침 적용세대가 총량제로 흐르는지·
다획지·graceful(구통계 없으면 어린이집 확인필요)을 검증한다.
"""

import httpx

from app.services import deliberation, survey
from app.schemas.survey import SurveyResult, SurveyDong


def _fake_survey(sgg="11590", applied_hh=28829, applied_pop=53751):
    return SurveyResult(
        address="a", site_dong="본동", site_sgg=sgg, radius=1000, ym="202604",
        dongs=[SurveyDong(name="본동", ratio=0.99, total_pop=30000, total_hh=15000,
                          applied_pop=applied_pop, applied_hh=applied_hh, same_sgg=True)],
        applied_pop_total=applied_pop, applied_hh_total=applied_hh)


def test_assess_flows_applied_hh_into_quota(monkeypatch):
    monkeypatch.setattr(survey, "survey_area",
                        lambda a, radius=1000, ym=None, client=None: _fake_survey())
    monkeypatch.setattr(deliberation, "_gu_infant", lambda sgg: 9652)
    monkeypatch.setattr(deliberation, "_gu_households", lambda sgg: 188042)

    a = deliberation.assess_quota("서울 동작구 본동 441", 981,
                                  existing_area={"작은도서관": 1000.16, "어린이집": 5728.0},
                                  planned_area={"작은도서관": 515.92}, client=httpx.Client())
    assert a.site_sgg == "11590" and a.gu_infant == 9652 and a.gu_households == 188042
    assert len(a.results) == 1
    q = a.results[0]
    assert q.applied_households == 28829
    lib = next(f for f in q.facilities if f.name == "작은도서관")
    # 걸침 적용세대(28829)가 산정에 흘러 동작 실측 3471.34 재현
    assert abs(lib.required_area - 3471.34) < 0.1
    assert lib.verdict == "부족시설"
    cc = next(f for f in q.facilities if f.name == "어린이집")
    assert cc.verdict in ("부족시설", "충족시설")  # 구통계 있으니 산정됨


def test_multi_parcel(monkeypatch):
    monkeypatch.setattr(survey, "survey_area",
                        lambda a, radius=1000, ym=None, client=None: _fake_survey(applied_hh=45375))
    monkeypatch.setattr(deliberation, "_gu_infant", lambda sgg: 17099)
    monkeypatch.setattr(deliberation, "_gu_households", lambda sgg: 222940)
    a = deliberation.assess_quota("강동 삼익", [409, 581], client=httpx.Client())
    assert len(a.results) == 2
    assert a.results[0].label == "획지1" and a.results[0].new_households == 409
    assert a.results[1].label == "획지2" and a.results[1].new_households == 581
    # 걸침 적용세대는 공유
    assert a.results[0].applied_households == 45375 == a.results[1].applied_households


def test_graceful_without_gu_stats(monkeypatch):
    monkeypatch.setattr(survey, "survey_area",
                        lambda a, radius=1000, ym=None, client=None: _fake_survey())
    monkeypatch.setattr(deliberation, "_gu_infant", lambda sgg: None)
    monkeypatch.setattr(deliberation, "_gu_households", lambda sgg: None)
    a = deliberation.assess_quota("서울 동작구 본동 441", 981, client=httpx.Client())
    assert any("확인필요" in n for n in a.notes)
    cc = next(f for f in a.results[0].facilities if f.name == "어린이집")
    assert cc.verdict == "확인필요"          # 영유아 없으니 추정 안 함 (절대 원칙 3)
    # 도서관·경로당은 구통계 불필요 → 정상 판정
    lib = next(f for f in a.results[0].facilities if f.name == "작은도서관")
    assert lib.verdict in ("부족시설", "충족시설")
