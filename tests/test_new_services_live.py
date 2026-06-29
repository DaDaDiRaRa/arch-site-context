"""신규 5키 서비스 골격 실호출 테스트 (P14) — 키·네트워크 있을 때만.

KMA(날씨)·RONE(부동산지수)·SEOUL(생활인구)·NEIS(학교)·KOPIS(공연시설).
검증된 엔드포인트(docs/API_VERIFICATION) 기반. 미승인/미등록은 graceful skip.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()


# ── KMA ──────────────────────────────────────────────────────────
@pytest.mark.skipif(not os.getenv("KMA_KEY"), reason="KMA_KEY 미설정")
def test_kma_weather() -> None:
    from app.services import kma

    d, notes = kma.fetch_weather(37.5260, 126.9244)
    if d is None:
        pytest.skip(f"기상청 응답 없음: {notes}")
    assert d["nx"] and d["ny"]
    assert d["temp_c"] is None or -50 < d["temp_c"] < 60


def test_kma_grid_conversion() -> None:
    """좌표→격자 변환은 키 없이도 결정적 (서울시청 ≈ 60,127)."""
    from app.services import kma

    nx, ny = kma.dfs_xy(37.5663, 126.9779)
    assert nx == 60 and ny == 127


# ── RONE ─────────────────────────────────────────────────────────
@pytest.mark.skipif(not os.getenv("RONE_KEY"), reason="RONE_KEY 미설정")
def test_rone_price_index() -> None:
    from app.services import rone

    d, notes = rone.fetch_price_index("영등포구")
    if d is None:
        pytest.skip(f"부동산원 응답 없음: {notes}")
    assert d["value"] > 0
    assert d["period"]  # yyyymm
    assert "영등포" in d["region"]


# ── NEIS ─────────────────────────────────────────────────────────
@pytest.mark.skipif(not os.getenv("NEIS_KEY"), reason="NEIS_KEY 미설정")
def test_neis_schools() -> None:
    from app.services import neis

    d, notes = neis.fetch_schools("서울특별시", "영등포구")
    if d is None:
        pytest.skip(f"NEIS 응답 없음: {notes}")
    assert d["count"] > 0
    assert d["by_level"]
    assert d["scope"] == "서울특별시 영등포구"


def test_neis_unknown_sido() -> None:
    from app.services import neis

    d, notes = neis.fetch_schools("없는도")
    assert d is None
    assert notes and "코드 미확인" in notes[0]


# ── SEOUL 생활인구 ───────────────────────────────────────────────
@pytest.mark.skipif(not os.getenv("SEOUL_API_KEY"), reason="SEOUL_API_KEY 미설정")
def test_seoul_living_population() -> None:
    from app.services import seoul

    d, notes = seoul.fetch_living_population("11560540")  # 여의동
    if d is None:
        pytest.skip(f"서울 생활인구 응답 없음: {notes}")
    assert d["value"] > 0
    assert d["date"]


def test_seoul_non_seoul_skipped() -> None:
    from app.services import seoul

    d, notes = seoul.fetch_living_population("26110680")  # 부산 코드
    assert d is None
    assert notes and "서울" in notes[0]


@pytest.mark.skipif(not os.getenv("KAKAO_KEY"), reason="KAKAO_KEY 미설정")
def test_seoul_auto_resolve_from_coord() -> None:
    """좌표 → 카카오 행정동코드 H[:8] 자동 해석 → 생활인구."""
    from app.services import seoul

    d, notes = seoul.fetch_living_population(lat=37.5260, lon=126.9244)  # 여의도
    if d is None:
        pytest.skip(f"자동해석/데이터 없음: {notes}")
    assert d["dong_code"].startswith("1156")  # 영등포구 행정동
    assert d["value"] > 0


# ── KOPIS ────────────────────────────────────────────────────────
@pytest.mark.skipif(not os.getenv("KOPIS_KEY"), reason="KOPIS_KEY 미설정")
def test_kopis_venues_graceful() -> None:
    """KOPIS — 작동 시 시설 목록, 키 미등록(02)이면 graceful None+note."""
    from app.services import kopis

    d, notes = kopis.fetch_venues()
    if d is None:
        # 현재 키 returncode 02 상태 — 정직한 note 확인
        assert notes and ("KOPIS" in notes[0] or "공연시설" in notes[0])
    else:
        assert d["count"] > 0
        assert d["venues"][0]["name"]
