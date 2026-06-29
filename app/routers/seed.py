"""대지분석 보드 합본 — POST /seed (INTEGRATION.md §4·§6).

주소 1회 해석(공유 site) → 신규 데이터 서비스(상권·학교·부동산지수·날씨·생활인구·공연시설)를
context 에 best-effort 로 채운다. 각 블록은 graceful — 한 소스 실패해도 나머지 반환 (절대 원칙 3).
law·knowledge 블록은 형제 앱(arch-law-diagnose·graph)이 채운다 (경계 — INTEGRATION §2).
값은 실제 API 에서만, 출처·notes 명시 (절대 원칙 1·4).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.errors import ErrorBlock
from app.schemas.project_seed import ProjectSeed
from app.schemas.seed import SeedRequest
from app.services import kma, kopis, neis, rone, sangwon, seoul
from app.services.cache import default_cache
from app.services.kakao import KakaoError
from app.services.site_seed import build_site

router = APIRouter(tags=["seed"])


def _error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorBlock(code=code, message=message).model_dump())


def _gather(label: str, fn, *args, **kwargs):
    """서비스 1블록 수집 — 예외도 graceful 로 흡수 (오케스트레이터 차원 보장, 절대 원칙 3).

    Returns (data, notes). 서비스 내부 try 를 넘어선 예상밖 예외도 여기서 막아 /seed 가 죽지 않게 한다.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 — 한 블록 실패가 전체를 막지 않도록 의도적 광범위 캐치
        return None, [f"{label}: 수집 실패 ({type(e).__name__})."]


@router.post("/seed", response_model=None)
def seed(req: SeedRequest):
    """주소 → 공유 site + context(신규 데이터 서비스 합본). 보드 통합 진입점."""
    # 1) 공유 site 해석 (resolve 1곳 + VWorld pnu) — site_seed 공통 빌더
    try:
        site = build_site(req.address)
    except KakaoError as e:
        return _error("ADDR_UNRESOLVED", f"주소 해석 불가: {e}")

    notes: list = []
    context: dict = {}
    cache = default_cache  # 동일 대지 반복 호출 시 업스트림 재호출·rate-limit 회피

    # 2) 상권 (소상공인시장진흥공단 B553077, 좌표+반경)
    context["stores"], n = _gather(
        "상권", sangwon.fetch_store_district, site.lat, site.lon, req.radius, cache=cache)
    notes += n

    # 3) 학교 (NEIS, 시도+시군구)
    context["schools"], n = _gather(
        "학교", neis.fetch_schools, site.sido, site.sigungu, cache=cache)
    notes += n

    # 4) 부동산 지수 (부동산원 R-ONE, 시군구명)
    context["real_estate_index"], n = _gather(
        "부동산지수", rone.fetch_price_index, site.sigungu, cache=cache)
    notes += n

    # 5) 날씨 (기상청, 좌표) — apihub 가 느려 timeout 짧게, 실패 시 graceful
    context["weather"], n = _gather(
        "날씨", kma.fetch_weather, site.lat, site.lon, cache=cache, timeout=12.0)
    notes += n

    # 6) 생활인구 (서울 전용) — 좌표로 행정동코드 자동 해석, 명시 코드 있으면 우선
    if req.adstrd_code:
        context["living_population"], n = _gather(
            "생활인구", seoul.fetch_living_population, req.adstrd_code, cache=cache)
        notes += n
    elif site.sgg_code.startswith("11"):
        context["living_population"], n = _gather(
            "생활인구", seoul.fetch_living_population, lat=site.lat, lon=site.lon, cache=cache)
        notes += n
    else:
        context["living_population"] = None

    # 7) 공연시설 (KOPIS) — 시군구명 필터(코드체계 미검증 → 이름매칭). 키 미등록(02)이면 graceful
    context["venues"], n = _gather(
        "공연시설", kopis.fetch_venues, sido=site.sido, sigungu=site.sigungu, cache=cache)
    notes += n

    context["notes"] = notes

    # context = 터읽기 책임 영역. law·knowledge 는 형제 앱이 주입 (None 으로 자리만).
    return ProjectSeed(
        site=site,
        context=context,
        base_date=date.today().isoformat(),
    )
