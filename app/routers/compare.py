"""P9 후보지 비교 라우터 — POST /compare.

여러 후보지를 한 번에 A·B·P11로 읽어 나란히. 일부 주소 실패는 부분결과(site.error),
전부 실패면 ErrorBlock 하드블록 (추정 금지, 절대 원칙 3). 순위·점수 없음 — 판단은 사람.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas import CompareRequest, ErrorBlock
from app.schemas.facility import DEFAULT_KINDS
from app.services.compare import build_comparison

router = APIRouter(tags=["mode-p9"])

_MIN_SITES = 2
_MAX_SITES = 5


def _error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorBlock(code=code, message=message).model_dump())


@router.post("/compare", response_model=None)
def compare(req: CompareRequest):
    """후보지 비교. 주소 2~5개. 전부 실패하면 ErrorBlock."""
    addrs = [a.strip() for a in req.addresses if a and a.strip()]
    if len(addrs) < _MIN_SITES:
        return _error("TOO_FEW_SITES", f"비교하려면 후보지 주소가 {_MIN_SITES}개 이상 필요합니다.")
    if len(addrs) > _MAX_SITES:
        return _error("TOO_MANY_SITES", f"후보지는 최대 {_MAX_SITES}개까지 비교합니다.")

    kinds = req.kinds or list(DEFAULT_KINDS)
    result = build_comparison(addrs, req.use_type, req.radius, kinds)

    if all(s.error for s in result.sites):
        return _error("NO_DATA", "제공된 주소들로는 비교 불가 (모든 후보지 해석/데이터 실패).")
    return result
