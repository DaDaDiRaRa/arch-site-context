"""모드 A — 지역 통계 스키마.

출처: CLAUDE.md 6장 데이터 계약.
facts(수치)·implications(함의)는 코드/룩업이 만들고 LLM은 마지막 한 문단만 (절대 원칙 2).
모든 수치에 출처(통계표ID)·기준연도, 출력은 항상 '○○구 기준' (절대 원칙 4).
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Resolution = Literal["시군구", "읍면동"]


class AnalyzeRequest(BaseModel):
    """POST /analyze 입력."""

    address: str = Field(..., description="대지 주소", examples=["서울 영등포구 여의대로 24"])
    use_type: str = Field(
        ..., description="건물 용도 — matrix.json 키에 매칭", examples=["주거"]
    )
    year: Optional[int] = Field(
        None, description="기준연도. 미지정 시 최신 (KOSIS 최신 시점)", examples=[2024]
    )


class Region(BaseModel):
    """해석된 행정구역."""

    name: str = Field(..., examples=["영등포구"])
    code: str = Field(..., description="행정구역 코드", examples=["11560"])
    resolution: Resolution = Field(..., description="통계 해상도 (시군구/읍면동)")


class Fact(BaseModel):
    """통계 수치 1건. 코드/룩업이 만든다 (AI 추정 아님)."""

    item: str = Field(..., examples=["1인가구비율"])
    value: float = Field(..., examples=[38.2])
    national_avg: Optional[float] = Field(None, description="전국 평균(비교용)", examples=[33.4])
    unit: str = Field(..., examples=["%"])
    source_tbl: str = Field(..., description="출처 식별자 (KOSIS 통계표 ID 또는 API 출처명)", examples=["DT_1IN1502"])
    year: int = Field(..., description="기준연도 또는 측정연도", examples=[2024])
    source_type: Optional[str] = Field(None, description="데이터 소스 유형 (kosis|airkorea|data_go_kr|...)", examples=["kosis"])


class Implication(BaseModel):
    """함의. implications.json 규칙이 만든다 (LLM 아님). 판단은 사람 — '참고' 태그."""

    text: str = Field(..., examples=["소형 평형·공유공간 검토"])
    basis: str = Field(..., description="근거가 된 fact 항목", examples=["1인가구비율"])
    tag: str = Field("참고", examples=["참고"])


class RegionStat(BaseModel):
    """POST /analyze 출력 (모드 A)."""

    region: Region
    year: int = Field(..., examples=[2024])
    use_type: str = Field(..., examples=["주거"])
    facts: List[Fact]
    implications: List[Implication]
    draft_paragraph: str = Field(..., description="Claude 1회 서술 (또는 규칙 폴백)")
    source: Literal["ai", "rule_based_fallback"] = Field(
        "ai", description="문단 출처: ai 또는 rule_based_fallback"
    )
    notes: List[str] = Field(
        default_factory=list,
        description="투명성 메모 (예: 미확정 항목 건너뜀). no silent skip.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "region": {"name": "영등포구", "code": "11560", "resolution": "시군구"},
                    "year": 2024,
                    "use_type": "주거",
                    "facts": [
                        {
                            "item": "1인가구비율",
                            "value": 38.2,
                            "national_avg": 33.4,
                            "unit": "%",
                            "source_tbl": "DT_1IN1502",
                            "year": 2024,
                        }
                    ],
                    "implications": [
                        {
                            "text": "소형 평형·공유공간 검토",
                            "basis": "1인가구비율",
                            "tag": "참고",
                        }
                    ],
                    "draft_paragraph": (
                        "영등포구 기준, 1인가구 비율이 전국 평균보다 높게 나타난다. "
                        "(시군구 평균값이며 대지 고유값이 아님 — 참고용)"
                    ),
                    "source": "ai",
                }
            ]
        }
    }
