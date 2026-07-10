"""P10 물어보기 스키마 — 우리 데이터(A·B·P11) 위에서만 답하는 Q&A.

답은 실제로 가져온 번들 안에서만 만들고, 데이터로 답 못하면 '확인 불가'로 멈춘다
(절대 원칙 1·3, 환각 금지). LLM은 표현만(원칙 2). 데이터 밖은 사용자가 명시적으로
'웹에서 찾아보기'를 켤 때만 외부검색 — 결과는 '외부·참고' + 출처로 분리.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.diagnose import Diagnosis
from app.schemas.facility import DEFAULT_KINDS
from app.schemas.region import Fact, Region


class AskRequest(BaseModel):
    """POST /ask 입력."""

    address: str = Field(..., examples=["서울 영등포구 여의대로 24"])
    question: str = Field(..., examples=["고령인구 비율이 전국보다 높아?"])
    use_type: str = Field("주거", examples=["주거"])
    radius: int = Field(1000, ge=100, le=5000, examples=[1000])
    kinds: List[str] = Field(default_factory=lambda: list(DEFAULT_KINDS))
    web: bool = Field(False, description="opt-in 웹검색 폴백 (기본 꺼짐 — 데이터 위에서만)")


class WebSource(BaseModel):
    """웹검색 출처 (외부·참고)."""

    title: str = Field("", examples=["..."])
    url: str = Field(..., examples=["https://..."])


class AskResult(BaseModel):
    """POST /ask 출력 (P10)."""

    question: str
    answer: str
    answerable: bool = Field(..., description="제공된 데이터로 답 가능했나")
    source: str = Field(
        ..., description="ai(그라운디드) | ai_web(외부폴백) | no_data | ai_unavailable"
    )
    # 투명성: 답이 근거한 번들 그대로 노출 (출처 명시 — 절대 원칙 4)
    region: Optional[Region] = None
    facts: List[Fact] = Field(default_factory=list)
    counts: Dict[str, int] = Field(default_factory=dict)
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    web_sources: List[WebSource] = Field(default_factory=list)
    base_date: str = Field(..., examples=["2026-06-25"])
    notes: List[str] = Field(default_factory=list)
