"""대지 기본 정보 스키마 — POST /site.

위치 기반 부동산·건물 정보: 아파트 실거래가, 표준지 공시지가, 건축물대장.
값은 실제 API(국토부 data.go.kr)에서 호출해 가져온다 (절대 원칙 1).
추정 없음 — 데이터 없으면 null + notes (절대 원칙 3).
출처·기준연도 명시 (절대 원칙 4). 판단은 사람 (절대 원칙 5).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SiteRequest(BaseModel):
    """POST /site 입력."""

    address: str = Field(..., description="대지 주소", examples=["서울 영등포구 여의대로 24"])


class SiteCenter(BaseModel):
    """해석된 대지 위치."""

    lat: float
    lon: float
    address: str
    sido: str = ""
    sigungu: str = ""
    dong: str = ""


class Transaction(BaseModel):
    """실거래 1건 (매매·전월세 공통)."""

    category: str = Field(..., description="종류", examples=["토지매매", "아파트매매", "아파트전월세"])
    deal_type: str = Field("매매", description="거래유형", examples=["매매", "전세", "월세"])
    name: str = Field("", description="단지/건물명 (토지는 지목)", examples=["여의도파크원"])
    area_sqm: Optional[float] = Field(None, description="면적(㎡)", examples=[84.96])
    price_10k: Optional[int] = Field(None, description="매매금액 또는 보증금(만원)", examples=[85000])
    monthly_10k: Optional[int] = Field(None, description="월세(만원), 매매·전세는 None/0", examples=[180])
    floor: Optional[int] = Field(None, description="층", examples=[8])
    deal_ym: str = Field("", description="거래년월 YYYYMM", examples=["202605"])
    dong: str = Field("", description="법정동", examples=["여의도동"])
    note: str = Field("", description="부가 (토지: 용도지역, 연립: 주택유형)", examples=["제2종일반주거지역"])


class RealEstate(BaseModel):
    """실거래가 요약 (여러 종류 혼합)."""

    transactions: List[Transaction] = Field(default_factory=list)
    kinds: List[str] = Field(default_factory=list, description="조회한 종류")
    source: str = Field("국토부_실거래가(RTMS)", description="출처")
    period: str = Field("", description="조회 기간 (예: 최근 3개월)", examples=["최근 3개월"])
    note: str = Field("", description="주의사항")


class LandPrice(BaseModel):
    """개별공시지가 (좌표가 속한 필지)."""

    price_per_sqm: Optional[int] = Field(None, description="원/㎡", examples=[5800000])
    year: Optional[int] = Field(None, description="기준연도", examples=[2025])
    pnu: str = Field("", description="필지번호(PNU)")
    addr: str = Field("", description="필지 주소", examples=["서울특별시 영등포구 여의도동 24"])
    jibun: str = Field("", description="지번", examples=["24대"])
    source: str = Field("VWorld_개별공시지가", description="출처")
    note: str = Field("", description="주의사항")


class BuildingInfo(BaseModel):
    """건축물대장 기본 정보 (건축HUB, PNU 기준)."""

    name: Optional[str] = Field(None, description="건물명", examples=["에프케이아이타워"])
    purpose: Optional[str] = Field(None, description="주용도", examples=["업무시설"])
    floors_above: Optional[int] = Field(None, description="지상층수", examples=[20])
    floors_below: Optional[int] = Field(None, description="지하층수", examples=[3])
    year_built: Optional[int] = Field(None, description="사용승인연도", examples=[2005])
    total_area_sqm: Optional[float] = Field(None, description="연면적(㎡)", examples=[45230.5])
    site_area_sqm: Optional[float] = Field(None, description="대지면적(㎡)", examples=[1823.0])
    bcr: Optional[float] = Field(None, description="건폐율(%)", examples=[62.3])
    far: Optional[float] = Field(None, description="용적률(%)", examples=[395.0])
    source: str = Field("국토부_건축HUB_건축물대장", description="출처")
    note: str = Field("", description="주의사항")


class HazardExposure(BaseModel):
    """영향범위 내 1개 지표 (인구·가구·주택·사업체)의 영향/전체."""

    metric: str = Field(..., description="지표명", examples=["인구"])
    affected: Optional[int] = Field(None, description="영향범위 내 값", examples=[3840])
    total: Optional[int] = Field(None, description="기준 행정구역 전체 값", examples=[35508])
    unit: str = Field("", description="단위", examples=["명"])


class HazardZone(BaseModel):
    """위험지도 1종의 대지 영향범위 포함 여부 + 영향범위 내 지표 (홍수·산사태)."""

    in_zone: Optional[bool] = Field(
        None, description="대지가 속한 읍면동이 위험 영향범위에 포함되는지 (None=확인불가)", examples=[True]
    )
    affected_dong_count: Optional[int] = Field(
        None, description="같은 시군구 내 영향범위에 든 읍면동 수 (맥락)", examples=[13]
    )
    exposures: List[HazardExposure] = Field(
        default_factory=list, description="영향범위 내 지표(인구·가구·주택·사업체)의 영향/전체"
    )
    exposure_scope: str = Field(
        "", description="영향지표 집계 단위 (읍면동|시군구) — 일부 동/재해는 시군구 폴백", examples=["읍면동"]
    )


class HeatwaveHistory(BaseModel):
    """최근 여름 폭염특보 발효 이력 (SGIS #86 과거 폭염특보)."""

    alert_count: int = Field(0, description="경보 발효 건수", examples=[11])
    warning_count: int = Field(0, description="주의보 발효 건수", examples=[31])
    scope: str = Field("", description="매칭 단위 (시군구 또는 '○○ 광역(권역)')", examples=["서울 광역(권역)"])
    base_period: str = Field("", description="집계 기간", examples=["2024~2025 여름"])
    source: str = Field("SGIS_과거폭염특보", description="출처")


class SiteHazards(BaseModel):
    """대지 재해위험 — SGIS 위험지도 영향범위 포함 여부 + 폭염 이력 (위험 사실·참고, 판단은 사람)."""

    dong_name: str = Field("", description="판정 기준 읍면동", examples=["여의도동"])
    flood: HazardZone = Field(default_factory=HazardZone, description="홍수위험지도")
    landslide: HazardZone = Field(default_factory=HazardZone, description="산사태위험지도")
    heatwave: Optional[HeatwaveHistory] = Field(None, description="최근 여름 폭염특보 이력")
    base_year: str = Field("", description="위험지도 기준연도", examples=["2025"])
    source: str = Field("SGIS_재해위험지도", description="출처")
    note: str = Field(
        "위험지도 영향범위에 대지 읍면동이 포함되는지 여부(행정구역 단위·참고). 등급·심도 아님, 판단은 사람.",
        description="주의사항",
    )


class SiteInfo(BaseModel):
    """POST /site 출력 — 대지 기본 정보 (부동산·건물·재해위험)."""

    center: SiteCenter
    real_estate: RealEstate
    land_price: LandPrice
    building: BuildingInfo
    hazards: SiteHazards = Field(default_factory=SiteHazards, description="재해위험 (홍수·산사태)")
    base_date: str = Field(..., description="기준일 YYYY-MM-DD", examples=["2026-06-26"])
    notes: List[str] = Field(
        default_factory=list,
        description="투명성 메모 (미확인 데이터·API 오류 등). no silent skip.",
    )
