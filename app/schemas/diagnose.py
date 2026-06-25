"""P11 수급진단 스키마 — A(인구 수요) × B(시설 공급) 교차.

출처: CLAUDE.md §8(P11). 차별점: A·B 둘 다 있어야 가능한 조합.
demand(전국비교)·supply(반경 raw 개수)는 코드/규칙이 만들고, 부족/과잉은
휴리스틱이므로 모두 '참고' 태그 + 원수치 노출 (절대 원칙 2·5). 판단은 사람.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.facility import Center
from app.schemas.region import Region


class DiagnoseRequest(BaseModel):
    """POST /diagnose 입력."""

    address: str = Field(..., description="대지 주소", examples=["서울 영등포구 여의대로 24"])
    radius: int = Field(
        1000, description="진단 기준 반경(m). 보통 500/1000/2000.", examples=[1000]
    )


class DemandSignal(BaseModel):
    """수요 신호 (모드 A — 시군구 인구지표, 전국 대비)."""

    item: str = Field(..., examples=["유소년인구비율"])
    value: float = Field(..., examples=[8.3])
    national_avg: Optional[float] = Field(None, examples=[10.3])
    unit: str = Field(..., examples=["%"])
    level: str = Field(..., description="전국 대비 수준", examples=["낮음"])  # 높음|평이|낮음|불명
    source_tbl: str = Field(..., examples=["DT_1B04005N"])
    year: int = Field(..., examples=[2025])


class SupplySignal(BaseModel):
    """공급 신호 (모드 B — 반경 내 시설 개수)."""

    kinds: List[str] = Field(..., examples=[["어린이집", "유치원"]])
    count: int = Field(..., description="반경 내 합계 개수", examples=[12])
    radius: int = Field(..., examples=[1000])
    level: str = Field(..., description="공급 수준", examples=["보통"])  # 적음|보통|많음


class Diagnosis(BaseModel):
    """수급 진단 1건. 부족/과잉은 휴리스틱 — '참고'."""

    name: str = Field(..., examples=["보육시설 수급"])
    demand: DemandSignal
    supply: SupplySignal
    signal: str = Field(..., description="수요·공급 조합 분류", examples=["수요 낮음·공급 보통"])
    note: str = Field(..., description="수치 인용 한 줄 소견")
    tag: str = Field("참고", examples=["참고"])


class DiagnoseResult(BaseModel):
    """POST /diagnose 출력 (P11)."""

    center: Center
    region: Region = Field(..., description="수요 출처 시군구 (시군구 평균 — 절대 원칙 4)")
    radius: int = Field(..., examples=[1000])
    diagnoses: List[Diagnosis]
    source: str = Field("kakao+kosis", description="데이터 출처 (출처 명시 — 절대 원칙 4)")
    base_date: str = Field(..., description="기준일 YYYY-MM-DD", examples=["2026-06-25"])
    notes: List[str] = Field(
        default_factory=list,
        description="투명성 메모 (미확정 지표 건너뜀·커버리지 경고 등). no silent skip.",
    )
