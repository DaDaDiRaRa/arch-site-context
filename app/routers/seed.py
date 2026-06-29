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
from app.services.kakao import KakaoError
from app.services.site_seed import build_site

router = APIRouter(tags=["seed"])


def _error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorBlock(code=code, message=message).model_dump())


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

    # 2) 상권 (소상공인시장진흥공단 B553077, 좌표+반경)
    context["stores"], n = sangwon.fetch_store_district(site.lat, site.lon, req.radius)
    notes += n

    # 3) 학교 (NEIS, 시도+시군구)
    context["schools"], n = neis.fetch_schools(site.sido, site.sigungu)
    notes += n

    # 4) 부동산 지수 (부동산원 R-ONE, 시군구명)
    context["real_estate_index"], n = rone.fetch_price_index(site.sigungu)
    notes += n

    # 5) 날씨 (기상청, 좌표) — apihub 가 느려 timeout 짧게, 실패 시 graceful
    context["weather"], n = kma.fetch_weather(site.lat, site.lon, timeout=12.0)
    notes += n

    # 6) 생활인구 (서울 전용) — 좌표로 행정동코드 자동 해석, 명시 코드 있으면 우선
    if req.adstrd_code:
        context["living_population"], n = seoul.fetch_living_population(req.adstrd_code)
        notes += n
    elif site.sgg_code.startswith("11"):
        context["living_population"], n = seoul.fetch_living_population(lat=site.lat, lon=site.lon)
        notes += n
    else:
        context["living_population"] = None

    # 7) 공연시설 (KOPIS) — 키 미등록(02)이면 graceful
    context["venues"], n = kopis.fetch_venues()
    notes += n

    context["notes"] = notes

    # context = 터읽기 책임 영역. law·knowledge 는 형제 앱이 주입 (None 으로 자리만).
    return ProjectSeed(
        site=site,
        context=context,
        base_date=date.today().isoformat(),
    )
