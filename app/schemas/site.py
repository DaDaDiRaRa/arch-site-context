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


class AptTrade(BaseModel):
    """아파트 실거래가 1건."""

    apt_name: str = Field(..., examples=["여의도파크원"])
    area_sqm: float = Field(..., description="전용면적(㎡)", examples=[84.96])
    price_10k: int = Field(..., description="거래금액(만원)", examples=[85000])
    floor: Optional[int] = Field(None, description="층", examples=[8])
    deal_month: str = Field(..., description="거래년월 YYYYMM", examples=["202605"])
    dong: str = Field("", description="법정동", examples=["여의도동"])


class RealEstate(BaseModel):
    """아파트 실거래가 요약."""

    transactions: List[AptTrade] = Field(default_factory=list)
    source: str = Field("국토부_아파트실거래가(RTMS)", description="출처")
    period: str = Field("", description="조회 기간 (예: 최근 3개월)", examples=["최근 3개월"])
    note: str = Field("", description="주의사항")


class LandPrice(BaseModel):
    """표준지 공시지가."""

    price_per_sqm: Optional[int] = Field(None, description="원/㎡", examples=[5800000])
    year: Optional[int] = Field(None, description="기준연도", examples=[2025])
    pnu: str = Field("", description="필지번호(PNU)")
    source: str = Field("국토부_표준지공시지가", description="출처")
    note: str = Field("", description="주의사항")


class BuildingInfo(BaseModel):
    """건축물대장 기본 정보."""

    purpose: Optional[str] = Field(None, description="주용도", examples=["업무시설"])
    floors_above: Optional[int] = Field(None, description="지상층수", examples=[20])
    floors_below: Optional[int] = Field(None, description="지하층수", examples=[3])
    year_built: Optional[int] = Field(None, description="사용승인연도", examples=[2005])
    total_area_sqm: Optional[float] = Field(None, description="연면적(㎡)", examples=[45230.5])
    site_area_sqm: Optional[float] = Field(None, description="대지면적(㎡)", examples=[1823.0])
    bcr: Optional[float] = Field(None, description="건폐율(%)", examples=[62.3])
    far: Optional[float] = Field(None, description="용적률(%)", examples=[395.0])
    source: str = Field("국토부_건축물대장", description="출처")
    note: str = Field("", description="주의사항")


class SiteInfo(BaseModel):
    """POST /site 출력 — 대지 기본 정보 (부동산·건물)."""

    center: SiteCenter
    real_estate: RealEstate
    land_price: LandPrice
    building: BuildingInfo
    base_date: str = Field(..., description="기준일 YYYY-MM-DD", examples=["2026-06-26"])
    notes: List[str] = Field(
        default_factory=list,
        description="투명성 메모 (미확인 데이터·API 오류 등). no silent skip.",
    )
