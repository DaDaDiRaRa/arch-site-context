"""하드블록 에러 스키마.

데이터로 답할 수 없으면 추정하지 말고 '확인 불가'로 멈춘다 (절대 원칙 3, 환각 금지).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorBlock(BaseModel):
    """데이터 없을 때 하드블록 응답."""

    code: str = Field(..., description="에러 코드", examples=["NO_DATA"])
    message: str = Field(..., examples=["제공된 데이터로는 확인 불가"])

    model_config = {
        "json_schema_extra": {
            "examples": [{"code": "NO_DATA", "message": "제공된 데이터로는 확인 불가"}]
        }
    }
