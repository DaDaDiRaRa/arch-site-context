"""site_seed.build_site — PNU best-effort 가드 (네트워크 불필요).

build_site 의 docstring 은 "PNU는 best-effort(실패해도 빈 문자열로 진행 — 절대 원칙 3)"라고
약속하지만, 코드가 vworld.fetch_land_price 호출을 try/except 로 감싸지 않아 네트워크 예외가
그대로 새어나가던 결함(2026-07 리뷰 발굴, 2026-08-25 수정) — 이 테스트는 그 약속이 실제로
지켜지는지 검증한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.resolve import ResolvedAddress
from app.services.site_seed import build_site


def _loc() -> ResolvedAddress:
    return ResolvedAddress(
        address="서울특별시 영등포구 여의대로 24", lat=37.52, lon=126.92,
        bcode="1156010800", sgg_code="11560", sido="서울", sigungu="영등포구",
        eupmyeondong="여의동", notes=[],
    )


def test_pnu_fetch_exception_does_not_break_site_resolution() -> None:
    """fetch_land_price 가 네트워크 예외를 던져도 site 는 정상 반환(pnu 만 빈 문자열)."""
    with patch("app.services.site_seed.resolve_address", return_value=_loc()), \
         patch("app.services.site_seed.vworld.fetch_land_price", side_effect=TimeoutError("boom")):
        site = build_site("서울특별시 영등포구 여의대로 24", client=MagicMock())

    assert site.sgg_code == "11560"
    assert site.pnu == ""


def test_pnu_fetch_success_still_fills_pnu() -> None:
    with patch("app.services.site_seed.resolve_address", return_value=_loc()), \
         patch("app.services.site_seed.vworld.fetch_land_price",
               return_value=({"pnu": "1156010800100010000"}, [])):
        site = build_site("서울특별시 영등포구 여의대로 24", client=MagicMock())

    assert site.pnu == "1156010800100010000"


def test_with_pnu_false_skips_fetch_entirely() -> None:
    with patch("app.services.site_seed.resolve_address", return_value=_loc()), \
         patch("app.services.site_seed.vworld.fetch_land_price") as fetch:
        site = build_site("서울특별시 영등포구 여의대로 24", with_pnu=False, client=MagicMock())

    fetch.assert_not_called()
    assert site.pnu == ""
