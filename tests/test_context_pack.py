"""POST /context-pack 라우터 테스트 — 서비스 monkeypatch (CLAUDE.md §8.13 C6)."""

from fastapi.testclient import TestClient

from app.main import app
import app.routers.context_pack as router_mod
from app.schemas.quota import QuotaAssessment, QuotaResult, FacilityQuota
from app.schemas.survey import SurveyResult, SurveyDong, FacilityCategory
from app.services.kakao import KakaoError

client = TestClient(app)


def _fake_assessment():
    return QuotaAssessment(
        address="서울 동작구 본동 441", site_sgg="11590", radius=1000, ym="202606",
        gu_infant=7994, gu_households=188064,
        survey=SurveyResult(address="a", site_sgg="11590", radius=1000, ym="202606",
                            dongs=[SurveyDong(name="노량진1동", ratio=0.99, applied_hh=18264, same_sgg=True)],
                            applied_hh_total=30285, applied_pop_total=56000),
        facilities=[FacilityCategory(category="작은도서관", count=1)],
        results=[QuotaResult(label="", new_households=981, applied_households=30285,
                             facilities=[FacilityQuota(name="작은도서관", households=31266,
                                                       required_area=3690.0, legal_min=158,
                                                       legal_min_confidence="high", verdict="부족시설")])],
    )


def test_context_pack_ok(monkeypatch):
    monkeypatch.setattr(router_mod, "assess_quota", lambda *a, **k: _fake_assessment())
    r = client.post("/context-pack", json={"address": "서울 동작구 본동 441", "new_households": 981})
    assert r.status_code == 200
    body = r.json()
    assert body["site_sgg"] == "11590"
    assert body["survey"]["applied_hh_total"] == 30285
    assert body["results"][0]["facilities"][0]["verdict"] == "부족시설"


def test_context_pack_addr_error(monkeypatch):
    def boom(*a, **k):
        raise KakaoError("좌표 없음")
    monkeypatch.setattr(router_mod, "assess_quota", boom)
    r = client.post("/context-pack", json={"address": "없는주소", "new_households": 500})
    assert r.status_code == 422
    assert r.json()["code"] == "ADDR_UNRESOLVED"


def test_context_pack_no_dong(monkeypatch):
    empty = _fake_assessment()
    empty.survey.dongs = []
    monkeypatch.setattr(router_mod, "assess_quota", lambda *a, **k: empty)
    r = client.post("/context-pack", json={"address": "바다한가운데", "new_households": 500})
    assert r.status_code == 422
    assert r.json()["code"] == "NO_DATA"


def test_context_pack_pptx_url(monkeypatch):
    monkeypatch.setattr(router_mod, "assess_quota", lambda *a, **k: _fake_assessment())
    import app.services.deliberation_pptx as dpptx
    monkeypatch.setattr(dpptx, "build_pptx", lambda a, client=None: b"PK\x03\x04fake")
    r = client.post("/context-pack/pptx", json={"address": "서울 동작구 본동 441", "new_households": 981})
    assert r.status_code == 200
    body = r.json()
    assert body["url"].startswith("/files/packs/") and body["url"].endswith(".pptx")
    assert body["applied_households"] == 30285
    assert body["facilities"]["작은도서관"] == 1
