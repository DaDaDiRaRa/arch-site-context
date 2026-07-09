"""S3 — 대지 종합 읽기 라우터 (POST /board, CLAUDE.md §8.11).

기존 서비스(analyze·diagnose·site·seed)를 **병렬 오케스트레이션**해 한 객체로 합친다.
데이터·숫자는 전부 기존 서비스가 만든다 — /board 는 모으고, S2 교차시사점을 얹고, 결측을
투명하게 목록화만 한다 (재계산 금지·no silent skip, 절대 원칙 1·3). 종합점수·순위 없음.

주소는 1회 fail-fast 해석(build_site)으로 공유 Site·PNU 확보 후, 4개 도메인 브랜치를
동시에 돌린다. 각 브랜치는 graceful — 하나 실패해도 나머지로 보드를 채운다.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any, List, Optional, Tuple

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas import AnalyzeRequest, ErrorBlock
from app.schemas.board import BoardRequest, BoardResult, DomainCoverage
from app.schemas.site import SiteRequest
from app.services.cross_context import derive_cross_context
from app.services.diagnose import build_diagnosis
from app.services.kakao import KakaoError
from app.services.site_seed import build_site

router = APIRouter(tags=["board"])


def _error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorBlock(code=code, message=message).model_dump())


def _run(label: str, fn) -> Tuple[Optional[Any], List[str]]:
    """도메인 브랜치 1개 실행 — 예외·에러응답(JSONResponse) 둘 다 graceful 흡수.

    Returns (결과모델 또는 None, notes). 라우터 재사용 시 에러는 JSONResponse 로 오므로
    그 message 를 note 로 옮긴다 (확인 불가는 추정 않고 표기 — 절대 원칙 3).
    """
    try:
        r = fn()
        if isinstance(r, JSONResponse):
            try:
                msg = json.loads(bytes(r.body).decode()).get("message", "확인 불가")
            except Exception:  # noqa: BLE001
                msg = "확인 불가"
            return None, [f"{label}: {msg}"]
        return r, []
    except Exception as e:  # noqa: BLE001 — 한 브랜치 실패가 /board 를 막지 않도록
        return None, [f"{label}: 수집 실패 ({type(e).__name__})."]


@router.post("/board", response_model=None)
def board(req: BoardRequest):
    """대지 종합 읽기 — 인구·수급·재해·대지·생활맥락 + S2 교차시사점을 한 객체로."""
    # 1) 주소 1회 해석 (공유 Site·PNU, fail-fast 하드블록)
    try:
        site = build_site(req.address)
    except KakaoError as e:
        return _error("ADDR_UNRESOLVED", f"주소 해석 불가: {e}")
    if not site.sgg_code:
        return _error("NO_REGION_CODE", "시군구 코드를 확인할 수 없습니다.")

    # 2) 도메인 브랜치 — 기존 서비스/라우터를 그대로 재사용, 병렬 (지연 import 로 순환참조 회피)
    def _analyze():
        from app.routers.analyze import analyze
        return analyze(AnalyzeRequest(
            address=req.address, use_type=req.use_type,
            resolution=req.resolution, radius=req.radius,
        ))

    def _diagnose():
        return build_diagnosis(req.address, radius=req.radius, resolution=req.resolution)

    def _site():
        from app.routers.site import site_info
        return site_info(SiteRequest(address=req.address))

    def _seed():
        from app.routers.seed import seed
        from app.schemas.seed import SeedRequest
        return seed(SeedRequest(address=req.address, radius=req.radius))

    branches = [
        ("analyze", lambda: _run("인구 통계", _analyze)),
        ("diagnose", lambda: _run("수급진단", _diagnose)),
        ("site", lambda: _run("대지·재해", _site)),
        ("seed", lambda: _run("생활맥락", _seed)),
    ]
    results: dict = {}
    with ThreadPoolExecutor(max_workers=len(branches)) as ex:
        futs = {ex.submit(thunk): key for key, thunk in branches}
        for fut in as_completed(futs):
            results[futs[fut]] = fut.result()

    notes: List[str] = list(site_notes(site))
    a_res, n = results["analyze"]; notes += n
    d_res, n = results["diagnose"]; notes += n
    s_res, n = results["site"]; notes += n
    seed_res, n = results["seed"]; notes += n

    # 3) 각 브랜치에서 필요한 조각만 뽑아 담기 (값은 그대로 — 재계산 없음)
    facts = list(a_res.facts) if a_res else []
    implications = list(a_res.implications) if a_res else []
    region = a_res.region if a_res else None
    if a_res:
        notes += [x for x in a_res.notes if x not in notes]

    diagnoses = list(d_res.diagnoses) if d_res else []
    if d_res:
        notes += [x for x in d_res.notes if x not in notes]

    hazards = s_res.hazards if s_res else None
    land_price = s_res.land_price if s_res else None
    building = s_res.building if s_res else None
    real_estate = s_res.real_estate if s_res else None
    if s_res:
        notes += [x for x in s_res.notes if x not in notes]

    context = seed_res.context if seed_res else None

    # 4) ★ S2 교차규칙 — 통합 풀(인구+수급+재해) boolean 조합 (LLM 0, 새 숫자 0)
    cross = derive_cross_context(facts, diagnoses, hazards, use_type=req.use_type)

    # 4.5) ★ S4 종합 산출 두 블록 (opt-in) — 위 풀 위에서만. ①사실 해석 + ②AI 판단 (벽 분리·라벨)
    synthesis = None
    if req.synthesize:
        try:
            from app.services.synthesis import synthesize as _synthesize
            synthesis = _synthesize(req.use_type, facts, diagnoses, hazards, cross)
        except Exception as e:  # noqa: BLE001 — 종합 실패가 보드 전체를 막지 않도록
            notes.append(f"종합 산출(S4): 생성 실패 ({type(e).__name__}).")

    # 5) coverage — 도메인별 확보 여부 (no silent skip, 절대 원칙 3)
    coverage = _coverage(facts, diagnoses, hazards, land_price, building, context)

    return BoardResult(
        site=site,
        use_type=req.use_type,
        radius=req.radius,
        resolution=req.resolution,
        region=region,
        facts=facts,
        implications=implications,
        diagnoses=diagnoses,
        hazards=hazards,
        land_price=land_price,
        building=building,
        real_estate=real_estate,
        context=context,
        cross_implications=cross,
        coverage=coverage,
        synthesis=synthesis,
        base_date=date.today().isoformat(),
        notes=notes,
    )


def site_notes(site) -> List[str]:
    """build_site 자체는 notes 를 안 남기므로 자리만 (계약 안정)."""
    return []


def _hazard_state(hazards) -> str:
    """재해 확보 내용 요약 (in_zone 사실만)."""
    parts = []
    for label, zone in (("홍수", hazards.flood), ("산사태", hazards.landslide)):
        iz = zone.in_zone
        if iz is True:
            parts.append(f"{label} 영향범위 포함")
        elif iz is False:
            parts.append(f"{label} 영향범위 외")
    return " · ".join(parts) if parts else "위험지도 확인 불가"


def _coverage(facts, diagnoses, hazards, land_price, building, context) -> List[DomainCoverage]:
    """도메인별 확보 여부. 미확보도 사유와 함께 표기 (숨기지 않음 — 절대 원칙 3)."""
    cov: List[DomainCoverage] = []

    cov.append(DomainCoverage(
        domain="인구", available=bool(facts),
        detail=f"{len(facts)}개 지표" if facts else "확인 불가",
    ))
    cov.append(DomainCoverage(
        domain="수급", available=bool(diagnoses),
        detail=f"{len(diagnoses)}개 진단" if diagnoses else "확인 불가",
    ))

    haz_ok = bool(hazards) and (
        (hazards.flood.in_zone is not None) or (hazards.landslide.in_zone is not None)
    )
    cov.append(DomainCoverage(
        domain="재해", available=haz_ok,
        detail=_hazard_state(hazards) if hazards else "확인 불가",
    ))

    land_ok = bool(land_price and land_price.price_per_sqm is not None)
    bld_ok = bool(building and building.name)
    cov.append(DomainCoverage(
        domain="대지", available=land_ok or bld_ok,
        detail=(
            (f"공시지가 {land_price.price_per_sqm:,}원/㎡" if land_ok else "공시지가 미확보")
            + (f" · {building.name}" if bld_ok else "")
        ),
    ))

    ctx_keys = [k for k, v in (context or {}).items() if k != "notes" and v]
    cov.append(DomainCoverage(
        domain="생활맥락", available=bool(ctx_keys),
        detail=(f"{len(ctx_keys)}개 소스: " + ", ".join(ctx_keys)) if ctx_keys else "확인 불가",
    ))
    return cov
