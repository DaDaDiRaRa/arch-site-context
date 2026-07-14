"""C7 주변현황도 라우터 — POST /surroundings (CLAUDE.md §8.13).

대지 반경 내 여가·교육·주거·관공서·교통 시설 + 주변현황 서술문. 심의 슬라이드 4~6.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.schemas.errors import ErrorBlock
from app.services.kakao import KakaoError
from app.services.surroundings import collect_surroundings

router = APIRouter(tags=["deliberation"])


class SurroundingsRequest(BaseModel):
    address: str = Field(..., examples=["서울특별시 동작구 본동 441"])
    radius: int = Field(1000, description="주 반경(m)")


@router.post("/surroundings", response_model=None)
def surroundings(req: SurroundingsRequest):
    """주변현황 카테고리 + 서술문."""
    try:
        result = collect_surroundings(req.address, req.radius)
    except KakaoError as e:
        return JSONResponse(
            status_code=422,
            content=ErrorBlock(code="ADDR_UNRESOLVED", message=f"주소 해석 불가: {e}").model_dump(),
        )
    return result


@router.post("/surroundings/pptx", response_model=None)
def surroundings_pptx(req: SurroundingsRequest):
    """주변현황도 A3 PPTX 생성 → /files 저장 후 공유 URL 반환 (C7)."""
    import hashlib

    from app.config import OUT_DIR
    from app.services.surroundings_pptx import build_surroundings_pptx

    try:
        result = collect_surroundings(req.address, req.radius)
    except KakaoError as e:
        return JSONResponse(
            status_code=422,
            content=ErrorBlock(code="ADDR_UNRESOLVED", message=f"주소 해석 불가: {e}").model_dump(),
        )
    data = build_surroundings_pptx(result)
    packs_dir = OUT_DIR / "packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(f"surr|{req.address}|{req.radius}".encode()).hexdigest()[:12]
    fname = f"surroundings_{key}.pptx"
    (packs_dir / fname).write_bytes(data)
    return {"url": f"/files/packs/{fname}",
            "categories": {c.name: c.count for c in result.categories},
            "size_bytes": len(data)}
