"""C7 — 주변현황도 스키마 (CLAUDE.md §8.13, 심의 슬라이드 4~6).

대지 반경 내 여가·교육·주거·관공서·교통 시설을 카테고리별로 수집한 '주변현황'.
좌표·거리·개수=코드 계산 (절대 원칙 1·2). 서술문은 데이터 룰 조립(LLM 0).
도로폭·재개발 경계는 소스 미확보 → 안 만듦 (경계, 절대 원칙 3).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


class SurroundItem(BaseModel):
    """주변 시설 1건."""

    name: str
    addr: str = Field("", description="도로명주소")
    dist_m: int = Field(..., description="대지로부터 거리(m)")
    lat: float = 0.0
    lon: float = 0.0


class SurroundCategory(BaseModel):
    """주변현황 카테고리 (여가·교육·주거·관공서·교통)."""

    name: str = Field(..., examples=["교육"])
    count: int
    items: List[SurroundItem] = Field(default_factory=list)
    color: Tuple[int, int, int] = Field((120, 120, 120), description="위치도 핀·범례 색 RGB")
    notes: List[str] = Field(default_factory=list)


class SurroundingsResult(BaseModel):
    """주변현황도 데이터 (심의 슬라이드 5)."""

    address: str
    site_lat: float = 0.0
    site_lon: float = 0.0
    radius: int = Field(1000, description="주 반경(m)")
    ring_radii: List[int] = Field(default_factory=list, description="현황도 반경밴드(m)")
    categories: List[SurroundCategory] = Field(default_factory=list)
    narrative: str = Field("", description="주변현황 서술문 (데이터 룰 조립 — LLM 0)")
    notes: List[str] = Field(default_factory=list)
