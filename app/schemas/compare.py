"""P9 후보지 비교 스키마 — 여러 대지를 한 번에 나란히.

A(지역 통계)·B(주변 시설)·P11(수급진단)을 후보지별로 모아 비교. 정렬·필터는 프론트가
중립적으로 처리하며 '최고 후보지' 종합점수는 만들지 않는다 — 판단은 사람 (절대 원칙 5).
한 후보지가 실패해도 나머지는 계속 (error 필드로 정직하게 표시).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.diagnose import Diagnosis
from app.schemas.facility import DEFAULT_KINDS
from app.schemas.region import Fact, Region


class CompareRequest(BaseModel):
    """POST /compare 입력. 후보지 2~5개."""

    addresses: List[str] = Field(
        ..., description="후보지 주소 목록 (2~5개)",
        examples=[["서울 영등포구 여의대로 24", "서울 강남구 테헤란로 152"]],
    )
    use_type: str = Field("주거", description="건물 용도 (A 통계 + matrix)", examples=["주거"])
    radius: int = Field(1000, ge=100, le=5000, description="B·P11 반경(m)", examples=[1000])
    kinds: List[str] = Field(
        default_factory=lambda: list(DEFAULT_KINDS),
        description="B 표시용 시설종류", examples=[["어린이집", "경로당"]],
    )


class CompareSite(BaseModel):
    """후보지 1곳의 비교 데이터."""

    address: str = Field(..., description="입력 주소 (실패해도 보존)")
    region: Optional[Region] = Field(None, description="해석된 시군구 (실패 시 None)")
    facts: List[Fact] = Field(default_factory=list, description="A 지역 통계")
    counts: Dict[str, int] = Field(
        default_factory=dict, description="B: {시설종류: 반경 내 개수}"
    )
    diagnoses: List[Diagnosis] = Field(default_factory=list, description="P11 수급진단")
    error: Optional[str] = Field(None, description="이 후보지만 실패 시 사유 (나머지는 계속)")
    notes: List[str] = Field(default_factory=list)


class CompareResult(BaseModel):
    """POST /compare 출력 (P9)."""

    use_type: str = Field(..., examples=["주거"])
    radius: int = Field(..., examples=[1000])
    kinds: List[str] = Field(..., examples=[["어린이집", "경로당"]])
    sites: List[CompareSite]
    base_date: str = Field(..., description="기준일 YYYY-MM-DD", examples=["2026-06-25"])
