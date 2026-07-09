"""S2 — 교차규칙 엔진 스키마 (CLAUDE.md §8.11).

도메인 횡단 '참고' 시사점. implications.json 이 단일 지표(인구)만 봤다면, cross_context 는
통합 fact 풀(인구 + 수급 signal + 재해)을 **boolean 조합**으로 읽어 근거(basis) 달린 시사점을
만든다. 예: 고령↑ + 의료수급 적음 → "의료 접근성 검토".

**전부 규칙 매칭 · LLM 0 · 새 숫자 안 만듦** — 기존 fact 값을 조합·인용만 한다 (절대 원칙 1·2).
좋다/나쁘다 단정 없이 '재료'만 (절대 원칙 5). 각 basis 에 S1 근접도를 실어 "이 시사점이
대지에 얼마나 가까운 데이터에 근거하나"까지 투명하게 (절대 원칙 4).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.proximity import Proximity


class CrossBasis(BaseModel):
    """교차 시사점 1건이 근거로 삼은 fact 1개 (값 그대로 인용 — 새 숫자 없음)."""

    key: str = Field(..., description="근거 지표/신호 이름", examples=["고령인구비율"])
    detail: str = Field(..., description="값 그대로 인용", examples=["22.1% (전국 19.5%)"])
    proximity: Optional[Proximity] = Field(
        None, description="이 근거의 데이터 근접도 등급 (S1) — 대지>반경>읍면동>시군구>proxy", examples=["시군구"]
    )


class CrossImplication(BaseModel):
    """도메인 횡단 '참고' 시사점 1건. 조건이 모두 충족될 때만 생성."""

    name: str = Field(..., description="규칙 이름", examples=["의료 접근성"])
    text: str = Field(..., description="시사점 서술 ('참고' — 판단 아님)")
    basis: List[CrossBasis] = Field(..., description="근거 fact 들 (값·근접도 인용)")
    domains: List[str] = Field(
        ..., description="교차된 도메인 (인구|수급|재해)", examples=[["인구", "수급"]]
    )
    tag: str = Field("참고", examples=["참고"])
