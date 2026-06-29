"""대지분석 보드 합본 — POST /seed (INTEGRATION.md §4·§6).

주소 1회 해석(공유 site) → 신규 데이터 서비스(상권·학교·부동산지수·날씨·생활인구·공연시설)를
context 에 best-effort 로 채운다. 각 블록은 graceful — 한 소스 실패해도 나머지 반환 (절대 원칙 3).
law·knowledge 블록은 형제 앱(arch-law-diagnose·graph)이 채운다 (경계 — INTEGRATION §2).
값은 실제 API 에서만, 출처·notes 명시 (절대 원칙 1·4).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.errors import ErrorBlock
from app.schemas.project_seed import ProjectSeed
from app.schemas.seed import SeedRequest
from app.services import childcare, culture, kma, kopis, neis, rone, sangwon, seoul
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

    cache = default_cache  # 동일 대지 반복 호출 시 업스트림 재호출·rate-limit 회피

    # 수집 블록 — (context키, thunk). 각 thunk 은 _gather 로 (data, notes) 를 graceful 반환.
    # 모두 독립 소스 → 병렬 호출. 각 서비스가 자체 httpx.Client 생성 + 캐시는 소스별
    # distinct 파일키 → 스레드 안전. 콜드 순차 합계(~8s)를 가장 느린 1개 시간으로 단축.
    tasks: list = [
        # 2) 상권 (소상공인시장진흥공단 B553077, 좌표+반경)
        ("stores", lambda: _gather(
            "상권", sangwon.fetch_store_district, site.lat, site.lon, req.radius, cache=cache)),
        # 3) 학교 (NEIS, 시도+시군구)
        ("schools", lambda: _gather(
            "학교", neis.fetch_schools, site.sido, site.sigungu, cache=cache)),
        # 3b) 어린이집 (정보공개포털 cpmsapi021, 시군구코드) — 개수·총정원
        ("childcare", lambda: _gather(
            "어린이집", childcare.fetch_childcare, site.sgg_code, site.sigungu, cache=cache)),
        # 3c) 문화기반시설 (총람 B553457 10종, 시군구코드) — 유형별 개수·시설명
        ("culture", lambda: _gather(
            "문화시설", culture.fetch_culture, site.sgg_code, site.sigungu, cache=cache)),
        # 4) 부동산 지수 (부동산원 R-ONE, 시군구명)
        ("real_estate_index", lambda: _gather(
            "부동산지수", rone.fetch_price_index, site.sigungu, cache=cache)),
        # 5) 날씨 (기상청, 좌표) — apihub 가 느려 timeout 짧게, 실패 시 graceful
        ("weather", lambda: _gather(
            "날씨", kma.fetch_weather, site.lat, site.lon, cache=cache, timeout=12.0)),
        # 7) 공연시설 (KOPIS) — signgucode=행안부 sgg_code[:4]로 서버측 정확 필터(2026-06-29 검증).
        ("venues", lambda: _gather(
            "공연시설", kopis.fetch_venues, sido=site.sido, sigungu=site.sigungu,
            signgucode=site.sgg_code[:4] if site.sgg_code else None, cache=cache)),
    ]
    # 6) 생활인구 (서울 전용) — 명시 행정동코드 우선, 없으면 좌표로 자동 해석. 비서울은 None.
    if req.adstrd_code:
        tasks.append(("living_population", lambda: _gather(
            "생활인구", seoul.fetch_living_population, req.adstrd_code, cache=cache)))
    elif site.sgg_code.startswith("11"):
        tasks.append(("living_population", lambda: _gather(
            "생활인구", seoul.fetch_living_population, lat=site.lat, lon=site.lon, cache=cache)))

    # 병렬 실행 — _gather 가 예외를 흡수하므로 future.result() 는 항상 (data, notes).
    results: dict = {}
    with ThreadPoolExecutor(max_workers=len(tasks)) as ex:
        futs = {ex.submit(thunk): key for key, thunk in tasks}
        for fut in as_completed(futs):
            results[futs[fut]] = fut.result()

    # context 조립 — tasks 정의 순서대로 (notes 순서 안정·결정적).
    notes: list = []
    context: dict = {}
    for key, _ in tasks:
        data, n = results[key]
        context[key] = data
        notes += n
    context.setdefault("living_population", None)  # 비서울 → 자리만 (테스트·계약 보장)
    context["notes"] = notes

    # context = 터읽기 책임 영역. law·knowledge 는 형제 앱이 주입 (None 으로 자리만).
    return ProjectSeed(
        site=site,
        context=context,
        base_date=date.today().isoformat(),
    )
