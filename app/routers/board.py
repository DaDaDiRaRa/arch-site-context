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

    # 4.3) ★ T2 설계 드라이버 — 통합 풀을 증거강도로 랭킹 → 지배 드라이버 2~3개 (LLM 0)
    from app.services.design_drivers import derive_design_drivers
    drivers = derive_design_drivers(facts, diagnoses, hazards, use_type=req.use_type)

    # 4.4) ★ T1.5 대지 아키타입 — "이 동네는 ○○형" 규칙 룩업 (LLM 0)
    from app.services.archetype import classify_archetype
    archetype = classify_archetype(facts, diagnoses, hazards, use_type=req.use_type)

    # 4.45) ★ T3 프로그램 함의(POR) — 카테고리별 공간·프로그램 권고 (LLM 0)
    from app.services.program import derive_program
    program = derive_program(facts, diagnoses, hazards, use_type=req.use_type)

    # 4.5) ★ S4 종합 산출 두 블록 (opt-in) — 위 풀 위에서만. ①사실 해석 + ②AI 판단 (벽 분리·라벨)
    synthesis = None
    if req.synthesize:
        try:
            from app.services.synthesis import synthesize as _synthesize
            synthesis = _synthesize(req.use_type, facts, diagnoses, hazards, cross, drivers, archetype)
        except Exception as e:  # noqa: BLE001 — 종합 실패가 보드 전체를 막지 않도록
            notes.append(f"종합 산출(S4): 생성 실패 ({type(e).__name__}).")

    # 5) coverage — 도메인별 확보 여부 (no silent skip, 절대 원칙 3)
    coverage = _coverage(facts, diagnoses, hazards, land_price, building, context)

    result = BoardResult(
        site=site,
        use_type=req.use_type,
        radius=req.radius,
        resolution=req.resolution,
        region=region,
        archetype=archetype,
        facts=facts,
        implications=implications,
        diagnoses=diagnoses,
        hazards=hazards,
        land_price=land_price,
        building=building,
        real_estate=real_estate,
        context=context,
        cross_implications=cross,
        design_drivers=drivers,
        program_implications=program,
        coverage=coverage,
        synthesis=synthesis,
        base_date=date.today().isoformat(),
        notes=notes,
    )
    # 6) ★ T5 방법론·데이터 부록 — 실제로 흐른 출처·산정식·한계 각인 (LLM 0, 새 숫자 0)
    from app.services.methodology import build_methodology
    result.methodology = build_methodology(result)

    # 7) arch-site-model 물리 3D 결합 — assembler 가 넘긴 모델을 요약 (호출 안 함, provider 경계)
    if req.model is not None:
        from app.services.site_model import summarize_model
        result.model = summarize_model(req.model)

    # 계약(2단계): 제안서·형제앱 주입용 압축 투영 (원시 seed context 제외)
    if req.brief:
        from app.services.board_contract import board_brief
        return board_brief(result)
    return result


def site_notes(site) -> List[str]:
    """build_site 자체는 notes 를 안 남기므로 자리만 (계약 안정)."""
    return []


def _satellite_anchor(lat: float, lon: float, radius_m: int) -> Optional[str]:
    """대지 중심 위성 사진 + 반경 링 → JPEG data URI (지도 앵커). 실패 시 None (graceful)."""
    try:
        import base64
        import io
        import math

        from PIL import ImageDraw

        from app.services.tiles import compose_basemap

        z = {500: 16, 1000: 15, 2000: 14}.get(int(radius_m), 15)
        W, H = 720, 420
        img, _ = compose_basemap(lat, lon, z, W, H, "vworld")
        img = img.convert("RGBA")
        cx, cy = W // 2, H // 2
        mpp = 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)  # Web Mercator m/px
        rpx = radius_m / mpp if mpp else 0
        d = ImageDraw.Draw(img, "RGBA")
        if rpx:
            d.ellipse([cx - rpx, cy - rpx, cx + rpx, cy + rpx], outline=(230, 0, 18, 220), width=3)
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(230, 0, 18, 255), outline=(255, 255, 255, 255))
        out = io.BytesIO()
        img.convert("RGB").save(out, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.standard_b64encode(out.getvalue()).decode()
    except Exception:  # noqa: BLE001 — 지도 실패는 비치명, 보드는 지도 없이도 완결
        return None


def _massing_anchor(model) -> Optional[str]:
    """arch-site-model 건물 footprint → 축측(axonometric) 매싱 미리보기 JPEG data URI.

    geometry 가 이미 로컬 미터라 재투영 없이 이소 투영(2:1)만. three.js 없이 서버사이드 PIL —
    보드의 자체완결·오프라인 원칙 유지 (위성 앵커와 동일 패턴). 실패 시 None (graceful).
    """
    try:
        import base64
        import io

        from PIL import Image, ImageDraw

        fps = list(getattr(model, "footprints", None) or [])
        hs = list(getattr(model, "heights_m", None) or [])
        if not fps:
            return None
        W, H = 720, 420
        C, S = 0.866, 0.5  # 이소 투영 (x-y)·(x+y), z 위로

        def proj(x, y, z):
            return ((x - y) * C, (x + y) * S - z)

        allp: list = []
        prisms: list = []
        for i, fp in enumerate(fps):
            if len(fp) < 3:
                continue
            h = hs[i] if i < len(hs) else 0.0
            base = [proj(p[0], p[1], 0.0) for p in fp]
            roof = [proj(p[0], p[1], h) for p in fp]
            cx = sum(p[0] for p in fp) / len(fp)
            cy = sum(p[1] for p in fp) / len(fp)
            prisms.append((cx + cy, base, roof))
            allp.extend(base)
            allp.extend(roof)
        if not prisms:
            return None
        xs = [p[0] for p in allp]
        ys = [p[1] for p in allp]
        minx, miny = min(xs), min(ys)
        spanx = (max(xs) - minx) or 1.0
        spany = (max(ys) - miny) or 1.0
        m = 24
        sc = min((W - 2 * m) / spanx, (H - 2 * m) / spany)

        def to_screen(pt):
            return (m + (pt[0] - minx) * sc, m + (pt[1] - miny) * sc)

        img = Image.new("RGB", (W, H), (250, 250, 250))
        d = ImageDraw.Draw(img, "RGBA")
        prisms.sort(key=lambda t: t[0])  # painter: 뒤(작은 x+y) 먼저
        WALL, ROOF = (230, 0, 18, 55), (255, 255, 255, 235)
        EDGE, REDGE = (120, 120, 120, 200), (230, 0, 18, 190)
        for _, base, roof in prisms:
            bs = [to_screen(p) for p in base]
            rs = [to_screen(p) for p in roof]
            n = len(bs)
            for k in range(n):
                k2 = (k + 1) % n
                d.polygon([bs[k], bs[k2], rs[k2], rs[k]], fill=WALL, outline=EDGE)
            d.polygon(rs, fill=ROOF, outline=REDGE)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.standard_b64encode(out.getvalue()).decode()
    except Exception:  # noqa: BLE001 — 매싱 실패는 비치명, 보드는 3D 없이도 완결
        return None


@router.post("/board/view", response_model=None)
def board_view(req: BoardRequest):
    """대지 종합 읽기 → 공유·인쇄 가능한 한 장 HTML. /files 에 저장 후 공유 URL 반환 (T4)."""
    import hashlib

    from app.config import OUT_DIR
    from app.services.board_view import render_board_html

    # 전체 board 강제(brief=False) — 렌더는 facts 등 전체 필드 사용
    full = board(BoardRequest(**{**req.model_dump(), "brief": False}))
    if isinstance(full, JSONResponse):
        return full
    sat = _satellite_anchor(full.site.lat, full.site.lon, req.radius)
    mass = _massing_anchor(full.model) if full.model else None
    html_str = render_board_html(full.model_dump(), satellite_data_uri=sat, massing_data_uri=mass)

    boards_dir = OUT_DIR / "boards"
    boards_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(
        f"{req.address}|{req.use_type}|{req.radius}|{req.resolution}|{req.synthesize}|{full.base_date}".encode()
    ).hexdigest()[:12]
    fname = f"board_{key}.html"
    (boards_dir / fname).write_text(html_str, encoding="utf-8")
    return {
        "url": f"/files/boards/{fname}",
        "site": full.site.sigungu,
        "has_map": sat is not None,
        "base_date": full.base_date,
    }


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
