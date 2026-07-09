"""T3 — 프로그램 함의(POR seeds) 스키마 (CLAUDE.md §8.12).

건축 프로그래밍(pre-design) 관점: 맥락(인구·수급·재해)을 **건축 카테고리별 공간·프로그램 권고**로
번역한다. S2(교차시사점 '왜')·T2(지배 드라이버 '검토 신호')와 달리 T3 는 **"무엇을, 어느 카테고리에"**
= Program of Requirements 체크리스트 형태. 상용 아무도 안 함 = blue ocean.

전부 규칙 매칭·카테고리 룩업, **LLM 0·새 숫자 안 만듦**(원칙 1·2). '판정' 아닌 '검토 권고·참고'.
최종 프로그램 결정은 사람 (원칙 5).
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ProgramItem(BaseModel):
    """프로그램 권고 1건 — 건축 카테고리 + 구체 항목 + 근거."""

    category: str = Field(..., description="건축 카테고리", examples=["평면·세대"])
    recommendation: str = Field(..., description="공간·프로그램 권고 (검토 항목)")
    basis: List[str] = Field(..., description="근거가 된 사실/신호 이름", examples=[["1인가구비율"]])
    tag: str = Field("참고", examples=["참고"])
