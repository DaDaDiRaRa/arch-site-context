"""T5 — 방법론·데이터 부록 스키마 (CLAUDE.md §8.12).

이 보드의 수치가 **어디서·어떻게** 나왔는지 자동 부록. 공공 공모·감사 대비 —
사용한 데이터 출처·산정식·한계를 투명하게 각인한다 (절대 원칙 4). **새 숫자·LLM 0** —
BoardResult 에 이미 흐르는 출처(source_tbl·source·presence)를 모아 담을 뿐 (절대 원칙 1·2).
Esri 방법론 공개·토지이음 확인원 방식.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SourceEntry(BaseModel):
    """이 보드에 실제로 기여한 데이터 출처 1건 (기여한 것만 — no silent inclusion, 절대 원칙 3)."""

    key: str = Field(..., description="출처 식별자 (KOSIS 통계표 ID 또는 소스명)", examples=["DT_1B04005N"])
    name: str = Field(..., description="사람이 읽는 출처명", examples=["행정구역별/5세별 주민등록인구"])
    publisher: str = Field("", description="발간 기관", examples=["통계청 KOSIS"])
    api: str = Field("", description="호출 API/게이트웨이", examples=["KOSIS OpenAPI"])
    kind: str = Field("", description="유형 (통계표|API|지도|실시간 API 등)", examples=["통계표"])
    used_for: List[str] = Field(default_factory=list, description="이 출처가 채운 지표·도메인")
    years: List[int] = Field(default_factory=list, description="기여한 기준연도")
    proximity: Optional[str] = Field(
        None, description="이 출처 값의 대표(최상급) 근접도 등급 — S1", examples=["시군구"]
    )
    note: str = Field("", description="주의사항 (미등록 출처 등)")


class FormulaEntry(BaseModel):
    """이 보드에 등장한 파생 지표의 산정식 1건 (재현 가능·감사 대비)."""

    item: str = Field(..., description="지표 또는 파생량", examples=["고령인구비율"])
    formula: str = Field(..., description="산정식", examples=["(65세 이상 인구 ÷ 총인구) × 100"])
    note: str = Field("", description="부가 설명")


class Methodology(BaseModel):
    """T5 — 방법론·데이터 부록. 이 보드의 출처·산정식·한계 자동 각인 (LLM 0·새 숫자 0)."""

    summary: str = Field(..., description="방법론 한 줄 요약 (규칙 기반 — LLM 아님)")
    resolution: str = Field(..., description="인구/수요 산정 단위 (시군구|읍면동|반경)")
    sources: List[SourceEntry] = Field(
        default_factory=list, description="사용한 데이터 출처 (기여한 것만)"
    )
    formulas: List[FormulaEntry] = Field(
        default_factory=list, description="등장한 파생 지표 산정식"
    )
    limitations: List[str] = Field(
        default_factory=list, description="한계·주의 (평균값 캐비엇·확인불가·폴백·휴리스틱)"
    )
    base_date: str = Field("", description="기준일 YYYY-MM-DD")
