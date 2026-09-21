"""arch-site-model 층수 — 높이÷3.0 역산 대신 실측 floors 사용(층고 3.5 전환 회귀 방지, 2026-09-21)."""

from app.deck.map_slides import _floors


def test_uses_measured_floors_not_height():
    model = {"provenance": {"floor_height_m": 3.5}}
    assert _floors(model, {"floors": 10, "height": 35.0}) == 10   # 예전 방식이면 round(35/3.0)=12


def test_fallback_divides_by_response_floor_height():
    assert _floors({"provenance": {"floor_height_m": 3.5}}, {"floors": None, "height": 35.0}) == 10
    assert _floors({}, {"height": 30.0}) == 10                      # 구버전 응답(층고 3.0)
    assert _floors({}, {"height": 0.0}) == 1
