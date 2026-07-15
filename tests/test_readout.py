"""B2 — /readout 유닛 테스트 (네트워크 불필요, monkeypatch).

키 없는 CI 에서도 다차원 census 크랙·유형 프리셋·파생지표·**출처 필수(B1)** 회귀를 잡는다.
resolve·stats·census_multidim 을 가짜로 대체하고 build_readout 오케스트레이션을 검증한다.
값은 만들지 않는다 — mock 이 주는 실측 형태만 조립 (절대 원칙 1·3).
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _loc():
    return SimpleNamespace(
        notes=[], address="서울 영등포구 여의대로 24",
        sgg_code="11560", sigungu="영등포구", sido="서울",
        lat=37.52, lon=126.92,
    )


def _collect_facts(*a, **k):
    # 마지막 fact 는 출처가 없다 → B1 필터로 방출되면 안 됨 (절대 원칙 4).
    facts = [
        {"item": "총인구수", "value": 370000, "national_avg": None, "unit": "명",
         "source_tbl": "DT_1B04005N", "year": 2025},
        {"item": "고령인구비율", "value": 22.1, "national_avg": 19.5, "unit": "%",
         "source_tbl": "DT_1B04005N", "year": 2025},
        {"item": "세대수", "value": 180000, "national_avg": None, "unit": "세대",
         "source_tbl": "DT_1B040B3", "year": 2025},
        {"item": "출처없는지표", "value": 1.0, "unit": "x"},  # source_tbl 없음 → 필터돼야
    ]
    return facts, ["분석 단위: 시군구"], 2025


def _census(org, tbl, itm, sigungu, prd, **k):
    # biz·의료인력·아파트거래량은 값 있음, 나머지는 결측(None) — 결측도 출처와 함께 정직하게 방출.
    if tbl == "DT_1BD1032":
        return {"value": 96993, "breakdown": [["제조업", 1000], ["도소매", 800]], "year": "2021"}, []
    if tbl == "DT_HIRA4U":  # Phase3 의료인력
        return {"value": 8194, "breakdown": [], "year": "202601"}, []
    if tbl == "DT_408_2006_S0049":  # Phase3 아파트 거래량(월)
        return {"value": 977, "breakdown": [], "year": "202605"}, []
    if tbl == "DT_408_2006_S0040":  # Phase3 후속 주택 거래량(월)
        return {"value": 1167, "breakdown": [], "year": "202605"}, []
    return {"value": None, "breakdown": [], "year": None}, [f"{tbl}: 데이터 없음"]


def _patch(monkeypatch):
    monkeypatch.setattr("app.services.readout.resolve_address", lambda *a, **k: _loc())
    monkeypatch.setattr("app.services.readout.stats.collect_facts", _collect_facts)
    monkeypatch.setattr(
        "app.services.readout.census_multidim.fetch_census_indicator", _census)


# ── 정상 조립 + 유형 프리셋 강조 ─────────────────────────────────────────────
def test_readout_assembles(monkeypatch) -> None:
    _patch(monkeypatch)
    r = client.post("/readout", json={"address": "서울 영등포구 여의대로 24",
                                      "use_type": "주거", "project_type": "재개발"})
    assert r.status_code == 200
    b = r.json()
    assert b["site"]["sigungu"] == "영등포구"
    items = {d["item"] for d in b["demographics"]}
    assert {"총인구수", "고령인구비율", "세대수"} <= items
    # 재개발 프리셋 → 고령인구비율 강조
    hi = next(d for d in b["demographics"] if d["item"] == "고령인구비율")
    assert hi["emphasized"] is True


# ── B1: 출처·기준지역 필수 — 방출된 모든 숫자에 출처가 붙는다 ─────────────────
def test_readout_every_value_has_source(monkeypatch) -> None:
    _patch(monkeypatch)
    b = client.post("/readout", json={"address": "x", "project_type": "재건축"}).json()
    # 인구지표: 값이 있으면 출처·scope 필수
    for d in b["demographics"]:
        assert d["source_tbl"], f"{d['item']} 출처 없음"
        assert d["scope"] == "영등포구"
        assert d["scope_level"] == "시군구"
    # 출처 없던 fact 는 필터돼 방출 안 됨
    assert "출처없는지표" not in {d["item"] for d in b["demographics"]}
    # census 지표: 값이 있으면 출처 필수, 결측(None)은 출처와 함께 허용
    for c in b["context"]:
        assert c["source_tbl"], f"{c['label']} 출처 없음"
        if c["value"] is not None:
            assert c["source_tbl"]


# ── 파생지표: 실측 분모/분자 있을 때만 산출 (없으면 생략, 추정 안 함) ──────────
def test_readout_derived_only_when_data(monkeypatch) -> None:
    _patch(monkeypatch)
    b = client.post("/readout", json={"address": "x"}).json()
    labels = {d["label"] for d in b["derived"]}
    # 사업체수·총인구 있음 → 사업체밀도 산출
    assert "사업체밀도" in labels
    # 장애인·신혼부부 census 결측 → 관련 파생 없음 (억지 계산 안 함)
    assert "장애인비율" not in labels
    assert "신혼부부/세대" not in labels


# ── Phase3: 신규 census 지표(의료인력·아파트거래량) 편입 + 파생 ──────────────
def test_readout_phase3_indicators(monkeypatch) -> None:
    _patch(monkeypatch)
    b = client.post("/readout", json={"address": "x", "project_type": "재건축"}).json()
    ctx = {c["label"]: c for c in b["context"]}
    assert ctx["의료인력"]["value"] == 8194 and ctx["의료인력"]["source_tbl"] == "DT_HIRA4U"
    assert ctx["아파트 거래량(월)"]["value"] == 977
    assert ctx["주택 거래량(월)"]["value"] == 1167
    # 재건축 프리셋 → 아파트 거래량 강조
    assert ctx["아파트 거래량(월)"]["emphasized"] is True
    # 파생: 인구당 의료인력 (8194 / 370000 × 1000 = 22.1) · 아파트거래비중 (977/1167 = 83.7%)
    der = {d["label"]: d["value"] for d in b["derived"]}
    assert der["의료인력/천명"] == 22.1
    assert der["아파트거래비중"] == 83.7


# ── 알 수 없는 용도 = 하드블록 ───────────────────────────────────────────────
def test_readout_unknown_use_type_blocks(monkeypatch) -> None:
    _patch(monkeypatch)
    r = client.post("/readout", json={"address": "x", "use_type": "우주정거장"})
    assert r.status_code == 422
    assert r.json()["code"] == "NO_DATA"
