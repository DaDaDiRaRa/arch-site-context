"""P10 물어보기 라우터 — POST /ask.

우리 데이터(A·B·P11) 위에서만 답한다. 주소 해석 실패는 ErrorBlock 하드블록
(추정 금지, 절대 원칙 3). 데이터 밖 질문은 '확인 불가'(answerable=false), web=true 일 때만 외부폴백.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas import AskRequest, ErrorBlock
from app.services.ask import build_answer
from app.services.kakao import KakaoError

router = APIRouter(tags=["mode-p10"])


def _error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorBlock(code=code, message=message).model_dump())


@router.post("/ask", response_model=None)
def ask(req: AskRequest):
    """데이터 위에서만 답하는 Q&A. 주소 해석 불가면 ErrorBlock."""
    if not req.question.strip():
        return _error("EMPTY_QUESTION", "질문을 입력하세요.")
    try:
        return build_answer(req)
    except (KakaoError, ValueError) as e:
        return _error("ADDR_UNRESOLVED", f"주소 해석 불가: {e}")
