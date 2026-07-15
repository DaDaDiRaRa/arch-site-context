"""B2 — /seed 유닛 테스트 (네트워크 불필요, monkeypatch).

키 없는 CI 에서도 8블록 context 조립 + **graceful(한 소스 실패해도 나머지)** + notes 병합 +
living_population 자리(계약 보장)를 잡는다. 신규 데이터 서비스를 전부 가짜로 대체한다.
값은 만들지 않는다 — mock 형태만 조립 (절대 원칙 1·3).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.project_seed import Site

client = TestClient(app)


def _site(sgg_code="41135", sido="경기", sigungu="성남시 분당구"):
    return Site(address="경기 성남시 분당구 불정로 6", lat=37.35, lon=127.10,
                pnu="4113510300", bcode="4113510300", sgg_code=sgg_code,
                sido=sido, sigungu=sigungu, eupmyeondong="정자동")


def _patch(monkeypatch, site=None, **over):
    monkeypatch.setattr("app.routers.seed.build_site", lambda *a, **k: site or _site())
    defaults = {
        "sangwon.fetch_store_district": lambda *a, **k: ({"total": 2275}, []),
        "neis.fetch_schools": lambda *a, **k: (None, ["학교: 미확보"]),  # graceful None
        "childcare.fetch_childcare": lambda *a, **k: ({"count": 50, "capacity": 2785}, []),
        "culture.fetch_culture": lambda *a, **k: ({"total": 10}, []),
        "rone.fetch_price_index": lambda *a, **k: ({"index": 89.9}, []),
        "kma.fetch_weather": lambda *a, **k: ({"temp": 29}, []),
        "kopis.fetch_venues": lambda *a, **k: ({"total": 5}, []),
        "seoul.fetch_living_population": lambda *a, **k: ({"population": 191469}, []),
    }
    defaults.update(over)
    for path, fn in defaults.items():
        monkeypatch.setattr(f"app.routers.seed.{path}", fn)


# ── 정상 조립 (비서울 → living_population 자리만) ────────────────────────────
def test_seed_assembles(monkeypatch) -> None:
    _patch(monkeypatch)
    r = client.post("/seed", json={"address": "경기 성남시 분당구 불정로 6", "radius": 1000})
    assert r.status_code == 200
    b = r.json()
    ctx = b["context"]
    assert ctx["stores"]["total"] == 2275
    assert ctx["childcare"]["capacity"] == 2785
    assert ctx["real_estate_index"]["index"] == 89.9
    # 학교는 graceful None + note
    assert ctx["schools"] is None
    assert any("학교" in n for n in ctx["notes"])
    # 비서울 → 생활인구 자리만 (계약 보장)
    assert ctx["living_population"] is None
    # 형제앱 슬롯은 비어 있음 (경계)
    assert b.get("law") is None and b.get("knowledge") is None


# ── 서울 → 생활인구 좌표 자동 해석 ───────────────────────────────────────────
def test_seed_seoul_living_population(monkeypatch) -> None:
    _patch(monkeypatch, site=_site(sgg_code="11560", sido="서울", sigungu="영등포구"))
    b = client.post("/seed", json={"address": "서울 영등포구 여의대로 24"}).json()
    assert b["context"]["living_population"]["population"] == 191469


# ── graceful: 한 서비스가 예외를 던져도 /seed 는 200, 해당 블록만 None ────────
def test_seed_isolates_service_failure(monkeypatch) -> None:
    def _boom(*a, **k):
        raise RuntimeError("상권 API 500")
    _patch(monkeypatch, **{"sangwon.fetch_store_district": _boom})
    b = client.post("/seed", json={"address": "경기 성남시 분당구 불정로 6"}).json()
    assert b["context"]["stores"] is None
    assert any("상권" in n for n in b["context"]["notes"])
    # 나머지 블록은 정상
    assert b["context"]["culture"]["total"] == 10


# ── P13: 용도 지정 시 관련 소스만 호출 ───────────────────────────────────────
def test_seed_p13_filters_sources_by_use_type(monkeypatch) -> None:
    # 의료 프로파일 관련 소스만: stores·childcare·schools·real_estate_index·weather
    # (culture·venues·living_population 은 미호출)
    _patch(monkeypatch, site=_site(sgg_code="11560", sido="서울", sigungu="영등포구"))
    b = client.post("/seed", json={"address": "서울 영등포구 여의대로 24", "use_type": "의료"}).json()
    ctx = b["context"]
    assert ctx["stores"] is not None and ctx["childcare"] is not None
    # 무관 소스는 호출 안 됨 → context 에 없음(또는 None 자리)
    assert ctx.get("culture") is None and ctx.get("venues") is None
    # living_population 은 자리표시만 (계약 보장)
    assert ctx.get("living_population") is None
    assert any("P13" in n and "미호출" in n for n in ctx["notes"])


def test_seed_p13_none_calls_all(monkeypatch) -> None:
    # 미지정이면 전체 호출 (하위호환)
    _patch(monkeypatch)
    b = client.post("/seed", json={"address": "경기 성남시 분당구 불정로 6"}).json()
    ctx = b["context"]
    assert ctx["stores"] is not None and ctx["culture"] is not None


# ── 주소 해석 실패 = 하드블록 ────────────────────────────────────────────────
def test_seed_bad_address_blocks(monkeypatch) -> None:
    from app.services.kakao import KakaoError
    monkeypatch.setattr("app.routers.seed.build_site",
                        lambda *a, **k: (_ for _ in ()).throw(KakaoError("no result")))
    r = client.post("/seed", json={"address": "없는주소"})
    assert r.status_code == 422
    assert r.json()["code"] == "ADDR_UNRESOLVED"
