"""T2 — 설계 드라이버 합성 스키마 (CLAUDE.md §8.12).

분석의 종착점 = "이 대지를 알고 나면 설계는 무엇에 응답해야 하나" = 지배 설계 드라이버 2~3개.
리서치(site analysis synthesis diagram)가 지목한 다리다. 상용 아무도 안 함 = blue ocean.

통합 풀(인구 지수 + 수급 signal + 재해)을 **증거 강도로 랭킹**해 상위 드라이버를 뽑는다.
**전부 규칙·산술, LLM 0, 새 숫자 안 만듦** — 기존 값(지수·수준·in_zone)을 가중합할 뿐 (절대 원칙 1·2).
드라이버는 '판정'이 아니라 '검토 신호'다. 최종 설계 판단은 사람 (절대 원칙 5). 제안서 작성은
형제앱(competition) 영역 — 우리는 드라이버(재료)까지, 컨셉안은 안 만듦 (경계).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.proximity import Proximity


class DriverEvidence(BaseModel):
    """드라이버 1개를 뒷받침한 근거 signal 1건 (값 그대로 인용 + 근접도)."""

    key: str = Field(..., description="근거 지표/신호", examples=["고령인구비율"])
    detail: str = Field(..., description="값 그대로 인용", examples=["22.1% (지수 113·상회)"])
    proximity: Optional[Proximity] = Field(
        None, description="근거의 데이터 근접도 (S1)", examples=["시군구"]
    )


class DesignDriver(BaseModel):
    """지배 설계 드라이버 1건 — 증거 강도로 랭킹. '검토 신호'(판정·제안안 아님)."""

    rank: int = Field(..., description="증거 강도 순위 (1=가장 강함)", examples=[1])
    name: str = Field(..., description="드라이버 이름", examples=["접근성·무장애 동선"])
    response: str = Field(
        ..., description="설계 응답(검토 신호) — driver_rules.json, 새 숫자 없음"
    )
    strength: float = Field(
        ..., description="증거 강도 점수 (랭킹용·참고, 지수·수준·근접도 가중합)", examples=[3.5]
    )
    evidence: List[DriverEvidence] = Field(..., description="근거 signal 들 (값·근접도 인용)")
    tag: str = Field("참고", examples=["참고"])
