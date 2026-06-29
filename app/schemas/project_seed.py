"""project_seed.json 스키마 — 세 앱(터읽기·diagnose·graph) 공유 계약 (INTEGRATION.md §4).

주소 1회 해석 → 공유 `site`(좌표·법정동코드·PNU) 기준으로 각 앱이 자기 블록을 채운다.
터읽기는 `site` + `context`(인문·생활맥락)를 책임지고, `law`·`knowledge`는 형제 앱이 채운다.
형제 블록은 각 앱이 스키마 주인이므로 여기선 느슨한 dict로 둔다 (경계 — §2 중복금지).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Site(BaseModel):
    """세 앱이 공유하는 대지 식별자 — 한 곳에서 1회 해석 (좌표·코드 중복호출 제거)."""

    address: str = Field(..., description="정규화 주소", examples=["서울특별시 영등포구 여의대로 24"])
    lat: float
    lon: float
    pnu: str = Field("", description="필지고유번호 19자리 (VWorld 개별공시지가)")
    bcode: str = Field("", description="법정동코드 10자리")
    sgg_code: str = Field("", description="시군구코드 5자리")
    sido: str = ""
    sigungu: str = ""
    eupmyeondong: str = ""


class ProjectSeed(BaseModel):
    """대지분석 보드 합본 — 세 앱 결과를 좌표 기준으로 합친 한 덩어리."""

    site: Site
    context: Optional[dict] = Field(
        None, description="터읽기: RegionStat + FacilityResult + DiagnoseResult"
    )
    law: Optional[dict] = Field(
        None, description="arch-law-diagnose: 8카테고리 GREEN/YELLOW/RED + 용도지역 사실"
    )
    knowledge: Optional[dict] = Field(
        None, description="arch-law-graph: 근거 조문 노드 id 목록"
    )
    base_date: str = Field(..., description="기준일 YYYY-MM-DD")
