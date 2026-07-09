"""P11 수급진단 스키마 — A(인구 수요) × B(시설 공급) 교차.

출처: CLAUDE.md §8(P11). 차별점: A·B 둘 다 있어야 가능한 조합.
demand(전국비교)·supply(반경 raw 개수)는 코드/규칙이 만들고, 부족/과잉은
휴리스틱이므로 모두 '참고' 태그 + 원수치 노출 (절대 원칙 2·5). 판단은 사람.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.facility import Center
from app.schemas.proximity import Proximity, proximity_of
from app.schemas.region import Region, Resolution, compute_index, index_band


class DiagnoseRequest(BaseModel):
    """POST /diagnose 입력."""

    address: str = Field(..., description="대지 주소", examples=["서울 영등포구 여의대로 24"])
    radius: int = Field(
        1000, description="진단 기준 반경(m). 보통 500/1000/2000.", examples=[1000]
    )
    resolution: Resolution = Field(
        "시군구",
        description="수요(인구) 해상도. '읍면동'=동 단위(KOSIS). '반경'=radius 반경 내 실인구(SGIS 집계구 합산) — 수요·공급 같은 반경. SGIS 미제공 지표(1인가구 등)는 시군구 폴백",
        examples=["시군구"],
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
    scope: Optional[str] = Field(
        None, description="수요 기준 지역명 (예: '여의동' 또는 '영등포구')", examples=["영등포구"]
    )
    scope_level: Optional[str] = Field(
        None, description="수요 기준 해상도 (읍면동|시군구)", examples=["시군구"]
    )
    proximity: Optional[Proximity] = Field(
        None,
        description="수요 데이터 근접도 등급 (대지>반경>읍면동>시군구>proxy). scope_level에서 정규화 — S1",
        examples=["시군구"],
    )
    index: Optional[int] = Field(
        None, description="전국=100 지수 (value/national×100, 비율 지표만) — T1", examples=[81]
    )
    index_band: Optional[str] = Field(
        None, description="전국 대비 밴드 (상회|비슷|하회) — T1", examples=["하회"]
    )

    @model_validator(mode="after")
    def _fill_derived(self) -> "DemandSignal":
        if self.proximity is None:
            self.proximity = proximity_of(self.scope_level)
        if self.index is None:
            self.index = compute_index(self.value, self.national_avg, self.unit)
        if self.index_band is None:
            self.index_band = index_band(self.index)
        return self


class SupplySignal(BaseModel):
    """공급 신호 (모드 B — 반경 내 시설 개수). 일부 규칙은 시군구 정원(capacity) 보강.

    density_per_10k: 시군구 총인구 기준 만명당 시설수 (반경 개수 / (시군구총인구 / 10,000)).
    national_density_per_10k: 전국 만명당 시설수 (출처: supply_demand.json national_density_source).
    vs_national_pct: density / national × 100. 100 = 전국평균, 60 = 평균의 60%.
    ※ 분모는 시군구 총인구 — 반경 내 인구 추정치 아님. 상대비교·추세 참고용.
    """

    kinds: List[str] = Field(..., examples=[["어린이집", "유치원"]])
    count: int = Field(..., description="반경 내 합계 개수", examples=[12])
    radius: int = Field(..., examples=[1000])
    level: str = Field(..., description="공급 수준", examples=["보통"])  # 적음|보통|많음
    density_per_10k: Optional[float] = Field(
        None, description="시군구 총인구 만명당 반경 내 시설수 (참고)", examples=[3.6]
    )
    national_density_per_10k: Optional[float] = Field(
        None, description="전국 만명당 시설수 기준값 (출처: supply_demand.json)", examples=[7.7]
    )
    vs_national_pct: Optional[int] = Field(
        None, description="전국 기준 대비 % (100=평균, <100=평균이하)", examples=[47]
    )
    density_basis: str = Field(
        "", description="밀도 분모 기준: '반경'(반경 실인구·primary 판정) | '시군구'(시군구 총인구·참고) | ''(밀도없음)", examples=["반경"]
    )
    capacity: Optional[int] = Field(
        None, description="시군구 공급 정원(어린이집 정원 등 — 반경 아님, 참고)", examples=[2785]
    )
    capacity_scope: str = Field(
        "", description="정원 출처 범위 (시군구명 — 반경 개수와 단위 다름)", examples=["영등포구"]
    )
    proximity: Proximity = Field(
        "반경",
        description="공급 데이터 근접도 등급 — 개수는 항상 반경 내 실측이므로 '반경'. capacity(정원)만 시군구 (capacity_scope 참조) — S1",
        examples=["반경"],
    )


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
