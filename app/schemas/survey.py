"""C1 — 조사범위 걸침 합산 스키마 (CLAUDE.md §8.13 심의 현황팩).

심의도서 '조사대상범위 및 조사대상 행정동 인구·세대수 통계' 표를 재현한다.
반경에 걸치는 행정동을 **면적비율(걸침율)로 합산** — 걸침율=코드 기하(절대 원칙 1·2),
인구·세대=행안부 rdoa 실측(절대 원칙 1). 시군구 경계 넘는 동은 ⚠플래그(생활권 판단은 사람, 절대 원칙 5).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SurveyDong(BaseModel):
    """조사범위에 걸친 행정동 1개."""

    name: str = Field(..., description="행정동명", examples=["노량진1동"])
    hcode: Optional[str] = Field(None, description="행정기관코드(H10)")
    ratio: float = Field(..., description="걸침율 = 행정동 면적 대비 조사범위 교차비율 (0~1)")
    total_pop: Optional[int] = Field(None, description="행정동 총인구 (행안부 rdoa)")
    total_hh: Optional[int] = Field(None, description="행정동 총세대")
    applied_pop: Optional[int] = Field(None, description="적용인구 = 총인구 × 걸침율")
    applied_hh: Optional[int] = Field(None, description="적용세대 = 총세대 × 걸침율")
    same_sgg: Optional[bool] = Field(None, description="대지와 같은 시군구인가")
    flagged: bool = Field(False, description="타 시군구 등 생활권 검토 필요(⚠) — 계 제외")
    matched: bool = Field(True, description="행안부 인구·세대 매칭 성공 여부")


class SurveyFacility(BaseModel):
    """조사범위 내 시설 1건 (현황 목록용)."""

    name: str = Field(..., examples=["노량진1동 작은도서관"])
    addr: str = Field("", description="도로명주소 (카카오; VWorld 출처는 빈값)")
    dist_m: int = Field(..., description="대지 중심으로부터 거리(m)")
    src: str = Field("kakao", examples=["kakao", "vworld"])


class FacilityCategory(BaseModel):
    """조사범위 내 한 시설종류(도서관·경로당·어린이집) 현황."""

    category: str = Field(..., examples=["작은도서관"])
    count: int = Field(..., description="조사범위 내 개수")
    items: List[SurveyFacility] = Field(default_factory=list, description="시설 목록(거리순)")
    capacity: Optional[int] = Field(None, description="정원(어린이집만, 시군구 기준) — 참고")
    capacity_scope: Optional[str] = Field(None, description="정원 기준 지역 (시군구)")
    notes: List[str] = Field(default_factory=list, description="면적 미제공 등 정직한 메모")


class SurveyResult(BaseModel):
    """조사범위 걸침 합산 결과 (심의 인구·세대 통계표)."""

    address: str
    site_dong: str = Field("", description="대지 행정동명")
    site_sgg: str = Field("", description="대지 시군구코드 5자리")
    radius: int = Field(1000, description="조사범위 반경(m)")
    ym: str = Field("", description="인구·세대 기준 년월 YYYYMM")
    dongs: List[SurveyDong] = Field(default_factory=list, description="걸침 행정동 (걸침율 내림차순)")
    applied_pop_total: int = Field(0, description="적용인구 계 (대지 시군구 포함분)")
    applied_hh_total: int = Field(0, description="적용세대 계 (대지 시군구 포함분) — C2 총량제 입력")
    notes: List[str] = Field(default_factory=list)
