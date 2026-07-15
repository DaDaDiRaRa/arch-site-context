"""공동주택 대지 readout 스키마 — POST /readout.

재건축·재개발·민간발주 공동주택 부지의 시군구 인문·경제 맥락 종합 프로파일.
기존 matrix 지표(인구·가구) + 크랙한 census 지표(사업체·빈집·신혼부부·장애인) + 파생.
값은 실제 KOSIS (절대 원칙 1). 시군구 평균 — '○○구 기준' 명시 (절대 원칙 4). 판단은 사람 (원칙 5).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

# 프로젝트 유형 — 강조 프리셋만 다름, 데이터는 동일.
PROJECT_TYPES = ["재건축", "재개발", "민간", "주상복합"]


class ReadoutRequest(BaseModel):
    address: str = Field(..., description="대지 주소", examples=["서울 서초구 잠원동 60-3"])
    use_type: str = Field("주거", description="모드A 용도 (주거/상업/의료)")
    project_type: str = Field("재건축", description="프로젝트 유형(강조 프리셋)", examples=PROJECT_TYPES)


class ReadoutSite(BaseModel):
    lat: float
    lon: float
    address: str
    sigungu: str = ""
    sgg_code: str = ""


class DemographicFact(BaseModel):
    """기존 matrix 지표 (인구·가구) — 전국 대비.

    /readout 은 항상 시군구 평균이므로 scope_level 기본 '시군구' (절대 원칙 4).
    값이 있으면 출처(source_tbl)는 필수 — 출처 없는 숫자 금지 (절대 원칙 4).
    """

    item: str
    value: float
    national_avg: Optional[float] = None
    unit: str = ""
    source_tbl: str = Field(..., description="출처 통계표 ID (필수, 절대 원칙 4)")
    year: Optional[int] = None
    scope: Optional[str] = Field(None, description="기준 지역명 (예: '영등포구')")
    scope_level: str = Field("시군구", description="기준 해상도 — readout 은 항상 시군구 평균")
    emphasized: bool = False

    @model_validator(mode="after")
    def _require_source_for_value(self) -> "DemographicFact":
        if self.value is not None and not (self.source_tbl or "").strip():
            raise ValueError(f"{self.item}: 값이 있으면 출처(source_tbl) 필수 (절대 원칙 4)")
        return self


class ContextIndicator(BaseModel):
    """크랙한 census 지표 (산업·주거·복지). 일부는 분류구성(breakdown) 교차 포함.

    value 는 결측(None) 가능 — '조회했으나 데이터 없음'은 정직한 상태.
    단, 값이 있으면 출처(source_tbl)는 필수 (절대 원칙 4).
    """

    label: str
    value: Optional[int] = None
    unit: str = ""
    axis: str = Field("", description="분석축 (산업·고용/주거/복지 등)")
    breakdown: List[list] = Field(default_factory=list, description="분류구성 [[명, 값], …] (예: 산업대분류)")
    source_tbl: str = Field(..., description="출처 통계표 ID (필수, 절대 원칙 4)")
    year: Optional[str] = None
    scope: Optional[str] = Field(None, description="기준 지역명 (예: '영등포구')")
    scope_level: str = Field("시군구", description="기준 해상도 — readout 은 항상 시군구 평균")
    emphasized: bool = False

    @model_validator(mode="after")
    def _require_source_for_value(self) -> "ContextIndicator":
        if self.value is not None and not (self.source_tbl or "").strip():
            raise ValueError(f"{self.label}: 값이 있으면 출처(source_tbl) 필수 (절대 원칙 4)")
        return self


class DerivedIndicator(BaseModel):
    """파생지표 (정규화 — 분모: 총인구·세대수)."""

    label: str
    value: float
    unit: str = ""


class ReadoutResult(BaseModel):
    """POST /readout 출력 — 공동주택 대지 종합 프로파일."""

    site: ReadoutSite
    project_type: str
    demographics: List[DemographicFact] = Field(default_factory=list)
    context: List[ContextIndicator] = Field(default_factory=list)
    derived: List[DerivedIndicator] = Field(default_factory=list)
    base_date: str
    notes: List[str] = Field(default_factory=list, description="시군구 캐비엇·greenfield 경고·수집 실패 등")
