"""심의 현황팩 라우터 — POST /context-pack (CLAUDE.md §8.13 C6).

주소 + 신축세대 → 조사범위 걸침(C1) + 구 영유아·세대 + 주민공동시설 총량제 판정(C2).
서울시 통합심의 '커뮤니티 총량제 검토'를 자동 산정. 부족/충족은 '참고' — 최종 확정은 사람.
법정면적 tier confidence=low 는 조례 확인 필요 note 자동 부착 (절대 원칙 3·4·5).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.errors import ErrorBlock
from app.schemas.quota import ContextPackRequest
from app.services.deliberation import assess_quota
from app.services.kakao import KakaoError

router = APIRouter(tags=["deliberation"])


@router.post("/context-pack", response_model=None)
def context_pack(req: ContextPackRequest):
    """심의 커뮤니티 총량제 검토 산정."""
    try:
        result = assess_quota(
            req.address, req.new_households, radius=req.radius, ym=req.ym,
            existing_area=req.existing_area, planned_area=req.planned_area,
            labels=req.labels,
        )
    except KakaoError as e:
        return JSONResponse(
            status_code=422,
            content=ErrorBlock(code="ADDR_UNRESOLVED", message=f"주소 해석 불가: {e}").model_dump(),
        )

    if not result.survey.dongs:
        return JSONResponse(
            status_code=422,
            content=ErrorBlock(
                code="NO_DATA",
                message=f"조사범위 걸침 행정동을 찾지 못함 ({req.address}). 좌표/반경 확인.",
            ).model_dump(),
        )
    return result


@router.post("/context-pack/pptx", response_model=None)
def context_pack_pptx(req: ContextPackRequest):
    """심의 현황팩 A3 편집가능 PPTX 생성 → /files 저장 후 공유 URL 반환 (C4·C5)."""
    import hashlib
    import json

    from app.config import OUT_DIR
    from app.services.deliberation_pptx import build_pptx

    try:
        assessment = assess_quota(
            req.address, req.new_households, radius=req.radius, ym=req.ym,
            existing_area=req.existing_area, planned_area=req.planned_area, labels=req.labels,
        )
    except KakaoError as e:
        return JSONResponse(
            status_code=422,
            content=ErrorBlock(code="ADDR_UNRESOLVED", message=f"주소 해석 불가: {e}").model_dump(),
        )
    if not assessment.survey.dongs:
        return JSONResponse(
            status_code=422,
            content=ErrorBlock(code="NO_DATA",
                               message=f"조사범위 걸침 행정동을 찾지 못함 ({req.address}).").model_dump(),
        )

    data = build_pptx(assessment)
    packs_dir = OUT_DIR / "packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    hh_sig = "-".join(map(str, req.new_households if isinstance(req.new_households, list)
                          else [req.new_households]))
    # 캐시키에 면적·라벨도 포함 — 같은 주소·세대·반경이라도 면적 입력이 다르면 다른 파일(stale 방지)
    extra = json.dumps([req.existing_area, req.planned_area, req.labels], sort_keys=True,
                       ensure_ascii=False, default=str)
    key = hashlib.md5(
        f"{req.address}|{hh_sig}|{req.radius}|{assessment.ym}|{extra}".encode()).hexdigest()[:12]
    fname = f"pack_{key}.pptx"
    (packs_dir / fname).write_bytes(data)
    return {
        "url": f"/files/packs/{fname}",
        "site_sgg": assessment.site_sgg,
        "applied_households": assessment.survey.applied_hh_total,
        "facilities": {c.category: c.count for c in assessment.facilities},
        "size_bytes": len(data),
    }
