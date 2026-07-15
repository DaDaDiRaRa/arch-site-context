"""P11 수급진단 라우터 — POST /diagnose.

A(인구 수요)×B(시설 공급) 교차 진단. 데이터로 답 못하면 ErrorBlock 하드블록
(추정 금지, 절대 원칙 3). 부족/과잉은 휴리스틱 — 모두 '참고', 판단은 사람.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas import DiagnoseRequest, ErrorBlock
from app.services.diagnose import build_diagnosis
from app.services.kakao import KakaoError

router = APIRouter(tags=["mode-p11"])


def _error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorBlock(code=code, message=message).model_dump())


@router.post("/diagnose", response_model=None)
def diagnose(req: DiagnoseRequest):
    """수급진단. 수요 데이터가 하나도 없으면 ErrorBlock."""
    try:
        result = build_diagnosis(req.address, req.radius, resolution=req.resolution, use_type=req.use_type)
    except KakaoError as e:
        return _error("ADDR_UNRESOLVED", f"주소 해석 불가: {e}")

    if not result.diagnoses:
        return _error(
            "NO_DATA",
            f"제공된 데이터로는 수급진단 불가 ({result.region.name}). 수요지표 미확보.",
        )
    return result
