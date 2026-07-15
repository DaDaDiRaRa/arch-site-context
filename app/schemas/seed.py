"""POST /seed 입력 스키마 — 대지분석 보드 합본 진입점 (INTEGRATION.md).

주소 1회 해석 → 공유 site + 신규 데이터 서비스(상권·학교·부동산지수·날씨·생활인구·공연시설)를
context 에 best-effort 로 채운다. 출력은 schemas/project_seed.ProjectSeed.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SeedRequest(BaseModel):
    address: str = Field(..., description="대지 주소", examples=["서울특별시 영등포구 여의대로 24"])
    radius: int = Field(1000, ge=100, le=5000, description="상권 집계 반경(m)", examples=[500, 1000, 2000])
    adstrd_code: Optional[str] = Field(
        None, description="서울 생활인구용 행정동코드(8자리). 없으면 생활인구 생략", examples=["11560540"]
    )
    use_type: Optional[str] = Field(
        None, description="용도(분석 프로파일 또는 법적 용도). 지정 시 관련 context 소스만 호출(P13). 미지정이면 전체.",
        examples=["교육", "교육연구시설"],
    )
