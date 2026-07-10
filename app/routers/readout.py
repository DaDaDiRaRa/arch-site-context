"""공동주택 대지 readout 라우터 — POST /readout.

재건축·재개발·민간발주 공동주택 부지의 시군구 종합 프로파일 (인구·산업·주거·복지 + 파생).
값은 실제 KOSIS (절대 원칙 1). 각 지표 graceful (절대 원칙 3). 판단은 사람 (원칙 5).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.errors import ErrorBlock
from app.schemas.readout import PROJECT_TYPES, ReadoutRequest
from app.services import readout
from app.services.kakao import KakaoError

router = APIRouter(tags=["readout"])


def _error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorBlock(code=code, message=message).model_dump())


@router.post("/readout", response_model=None)
def site_readout(req: ReadoutRequest):
    """대지 주소 + 프로젝트 유형 → 공동주택 대지 종합 readout."""
    from app.services.matrix import use_types
    if req.use_type not in use_types():
        return _error("NO_DATA", f"알 수 없는 용도: {req.use_type}")
    project_type = req.project_type if req.project_type in PROJECT_TYPES else "재건축"
    try:
        return readout.build_readout(req.address, req.use_type, project_type)
    except KakaoError as e:
        return _error("ADDR_UNRESOLVED", f"주소 해석 불가: {e}")
