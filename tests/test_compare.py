"""P9 후보지 비교 테스트.

전체 흐름은 resolve·stats·facilities 를 모킹해 결정적으로 검증. 한 후보지 실패가
전체를 막지 않고 error 로 격리되는지(정직성)와, 종합점수 없이 후보지별 A·B·P11 이
나란히 담기는지 확인. 라이브는 키 있을 때만.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from app.schemas.facility import Center, FacilityResult
from app.services import compare
from app.services.kakao import KakaoError

load_dotenv()


class _Loc:
    def __init__(self, sgg, sigungu, addr):
        self.sgg_code, self.sigungu, self.address = sgg, sigungu, addr
        self.lat, self.lon = 37.5, 127.0
        self.notes: list = []


def _fake_resolve(address, client=None):
    if "bad" in address:
        raise KakaoError("주소를 해석할 수 없습니다 (모의 실패).")
    return _Loc("11560", "영등포구", address)


def _fake_facts(sgg, use_type, *a, **k):
    return ([{"item": "고령인구비율", "value": 19.2, "national_avg": 21.2, "unit": "%",
             "source_tbl": "DT_1B04005N", "year": 2025}], [], 2025)


def _fake_demand(sgg, items, *a, **k):
    return ([{"item": "유소년인구비율", "value": 8.3, "national_avg": 10.3, "unit": "%",
             "source_tbl": "DT_1B04005N", "year": 2025},
            {"item": "고령인구비율", "value": 19.2, "national_avg": 21.2, "unit": "%",
             "source_tbl": "DT_1B04005N", "year": 2025},
            {"item": "1인가구비율", "value": 45.1, "national_avg": 36.1, "unit": "%",
             "source_tbl": "DT_1JC1511", "year": 2024}], [], 2025)


def _fake_facility(address, kinds, radii, client=None, loc=None):
    band = {k: 5 for k in kinds}  # 모든 종류 5개
    return FacilityResult(
        center=Center(lat=37.5, lon=127.0, address=address),
        results=[], counts={str(radii[0]): band},
        source="kakao", base_date="2026-06-25", notes=[],
    )


def _patch(monkeypatch):
    monkeypatch.setattr(compare, "resolve_address", _fake_resolve)
    monkeypatch.setattr(compare.stats, "collect_facts", _fake_facts)
    monkeypatch.setattr(compare.stats, "collect_facts_by_items", _fake_demand)
    monkeypatch.setattr(compare, "build_facility_result", _fake_facility)


def test_comparison_aligns_sites(monkeypatch) -> None:
    _patch(monkeypatch)
    res = compare.build_comparison(
        ["서울 영등포구 여의대로 24", "서울 강남구 테헤란로 152"],
        use_type="주거", radius=1000, kinds=["어린이집", "경로당"],
    )
    assert len(res.sites) == 2
    for s in res.sites:
        assert s.error is None
        assert s.region.name == "영등포구"
        assert any(f.item == "고령인구비율" for f in s.facts)  # A
        assert s.counts == {"어린이집": 5, "경로당": 5}          # B (선택 종류만)
        assert len(s.diagnoses) >= 1                            # P11
        assert all(d.tag == "참고" for d in s.diagnoses)        # 판단은 사람


def test_comparison_isolates_failing_site(monkeypatch) -> None:
    _patch(monkeypatch)
    res = compare.build_comparison(
        ["서울 영등포구 여의대로 24", "bad address 잘못"],
        use_type="주거", radius=1000, kinds=["어린이집"],
    )
    ok, bad = res.sites[0], res.sites[1]
    assert ok.error is None and ok.region is not None  # 정상 후보지는 계속
    assert bad.error and bad.region is None            # 실패는 격리 (정직 표시)


def test_compare_endpoint_too_few_sites() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/compare", json={"addresses": ["서울 영등포구 여의대로 24"], "use_type": "주거"})
    assert r.status_code == 422
    assert r.json()["code"] == "TOO_FEW_SITES"


# ── 라이브 (키 있을 때만) ────────────────────────────────────────────────
@pytest.mark.skipif(
    not (os.getenv("KOSIS_KEY") and os.getenv("KAKAO_KEY")),
    reason="KOSIS_KEY/KAKAO_KEY 미설정 — 실호출 skip",
)
def test_compare_endpoint_real() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/compare", json={
        "addresses": ["서울 영등포구 여의대로 24", "서울 강남구 테헤란로 152"],
        "use_type": "주거", "radius": 1000, "kinds": ["어린이집", "경로당"],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["sites"]) == 2
    ok = [s for s in body["sites"] if not s["error"]]
    assert len(ok) >= 1
    for s in ok:
        assert s["region"]["resolution"] == "시군구"
        assert "어린이집" in s["counts"]
