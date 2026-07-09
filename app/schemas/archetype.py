"""T1.5 — 대지 아키타입(동네 유형) 스키마 (CLAUDE.md §8.12).

Esri Tapestry 의 "이 동네는 ○○형" legibility 를 규칙 기반으로. ⚠️ K-means(통계 클러스터=해석)는
쓰지 않는다 — 그건 절대 원칙 1 위반. 대신 **결정론 규칙 룩업**(implications/driver 패턴)으로
evocative 한글 유형명 + 2계층(group) + 근거를 붙인다. 숫자는 안 만들고 기존 값 boolean/임계 조합만.

'판정'이 아니라 '유형 라벨·참고'. 최종 판단은 사람 (절대 원칙 5). 뚜렷한 지배 유형이 약하면
'혼합형'으로 폴백(억지 분류 안 함, 절대 원칙 3).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.proximity import Proximity


class ArchetypeEvidence(BaseModel):
    """유형 판정을 뒷받침한 근거 1건 (값 그대로 인용 + 근접도)."""

    key: str = Field(..., examples=["1인가구비율"])
    detail: str = Field(..., examples=["45.1% (지수 125·상회)"])
    proximity: Optional[Proximity] = Field(None, examples=["시군구"])


class Archetype(BaseModel):
    """대지가 속한 동네 유형 1건 (지배 유형). 규칙 매칭·'참고'."""

    name: str = Field(..., description="유형명 (evocative 한글)", examples=["1인가구 도심 임대권"])
    group: str = Field(..., description="상위 유형군 (2계층)", examples=["주거·1인"])
    description: str = Field(..., description="유형 설명 (규칙 템플릿·새 숫자 없음)")
    match_score: float = Field(..., description="매칭 강도 (근거 signal 가중합·참고)", examples=[2.0])
    evidence: List[ArchetypeEvidence] = Field(..., description="판정 근거 (값·근접도 인용)")
    alternatives: List[str] = Field(
        default_factory=list, description="차점 유형명들 (혼재 특성 — 참고)"
    )
    tag: str = Field("참고", examples=["참고"])
