"""S3 — /board 통합 진입점 스키마 (CLAUDE.md §8.11).

흩어진 출력(analyze·diagnose·site·seed)을 **하나의 "이 필지는 어떤 곳인가"**로 합친다.
새 데이터·새 숫자 0 — 기존 서비스 결과를 모아 담고, 그 위에 S2 교차시사점(cross_implications)과
결측/확인불가 목록(coverage)을 얹을 뿐 (절대 원칙 1·2). 종합점수·순위는 안 매김 (P9 원칙 유지).
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.archetype import Archetype
from app.schemas.cross_context import CrossImplication
from app.schemas.design_drivers import DesignDriver
from app.schemas.diagnose import Diagnosis
from app.schemas.program import ProgramItem
from app.schemas.project_seed import Site
from app.schemas.region import Fact, Implication, Region, Resolution
from app.schemas.site import BuildingInfo, LandPrice, RealEstate, SiteHazards


class BoardRequest(BaseModel):
    """POST /board 입력."""

    address: str = Field(..., description="대지 주소", examples=["서울 영등포구 여의대로 24"])
    use_type: str = Field(..., description="건물 용도 — matrix.json 키", examples=["주거"])
    radius: int = Field(1000, description="시설·상권 반경(m)", examples=[500, 1000, 2000])
    resolution: Resolution = Field(
        "시군구",
        description="인구/수요 해상도. '반경'=SGIS 집계구 실인구, '읍면동'=행정동, '시군구'=구 평균",
        examples=["시군구"],
    )
    synthesize: bool = Field(
        False,
        description="S4 종합 산출(①사실 해석 + ②AI 판단 두 블록) 생성 여부. Claude 2콜 — opt-in(기본 off)",
    )
    brief: bool = Field(
        False,
        description="압축 투영(board_brief) 반환 여부. 제안서·프롬프트·형제앱 주입용 — 원시 seed context 제외 (계약 board_brief/1.0)",
    )


class Synthesis(BaseModel):
    """S4 — 종합 산출 두 블록 (벽 분리·라벨, CLAUDE.md §8.11).

    ①과 ②는 성격이 다르다 — ①은 검증된 사실 위 그라운디드 서술('참고'), ②는 그 위 AI '의견'.
    벽 + 라벨로 사용자가 "사실"과 "AI 의견"을 혼동하지 않게 한다 (정직성 핵심). 둘 다 새 숫자 금지.
    """

    interpretation: str = Field(
        ..., description="① 사실 종합(해석) — 검증된 사실만 인용한 그라운디드 서술. '참고'"
    )
    interpretation_source: Literal["ai", "rule_based_fallback", "no_data"] = Field(
        "ai", description="① 출처: ai | rule_based_fallback | no_data(그라운딩 사실 없음)"
    )
    interpretation_model: str = Field("", description="① 생성 모델 (ai일 때)")

    judgment: str = Field(
        ..., description="② AI 판단(의견) — 근거 fact 인용·가정 명시·새 숫자 금지. 검증/재현 보장 없음"
    )
    judgment_source: Literal["ai", "rule_based_fallback", "no_data"] = Field(
        "ai", description="② 출처"
    )
    judgment_model: str = Field("", description="② 생성 모델 (ai일 때)")
    judgment_label: str = Field(
        ..., description="② 고정 라벨 — 사실과 혼동 방지 (코드가 항상 부착)"
    )


class DomainCoverage(BaseModel):
    """도메인별 데이터 확보 여부 — no silent skip (절대 원칙 3). 확인불가도 정직하게 표기."""

    domain: str = Field(..., description="도메인", examples=["인구"])
    available: bool = Field(..., description="데이터 확보 여부")
    detail: str = Field("", description="확보 내용 또는 미확보 사유", examples=["12개 지표"])


class BoardResult(BaseModel):
    """POST /board 출력 — 대지 종합 읽기 (기존 서비스 재사용·병렬 오케스트레이션).

    facts(근접도 부착)·diagnoses·hazards 는 기존 서비스가 만든 값 그대로. cross_implications 는
    S2 엔진이 그 위에서 boolean 조합한 '참고' 시사점. coverage 는 결측/확인불가 투명 목록.
    """

    schema_version: str = Field(
        "board/1.0", description="계약 버전 — 형제앱(competition·MCP·site-model)이 guard"
    )
    site: Site = Field(..., description="공유 대지 식별자 (좌표·pnu·코드)")
    use_type: str
    radius: int
    resolution: str
    region: Optional[Region] = Field(None, description="인구/수요 산정 단위 (시군구/읍면동/반경)")
    archetype: Optional[Archetype] = Field(
        None, description="★ T1.5 대지 아키타입(동네 유형) — 규칙 룩업 '이 동네는 ○○형'"
    )

    facts: List[Fact] = Field(default_factory=list, description="인구 통계 (근접도 부착 — S1)")
    implications: List[Implication] = Field(
        default_factory=list, description="단일 지표 함의 (implications.json)"
    )
    diagnoses: List[Diagnosis] = Field(default_factory=list, description="수급진단 (A×B)")
    hazards: Optional[SiteHazards] = Field(None, description="재해위험 (홍수·산사태·폭염)")
    land_price: Optional[LandPrice] = Field(None, description="개별공시지가 (대지)")
    building: Optional[BuildingInfo] = Field(None, description="건축물대장 (대지)")
    real_estate: Optional[RealEstate] = Field(None, description="실거래 (참고)")
    context: Optional[dict] = Field(None, description="생활맥락 (상권·학교·문화·부동산지수·날씨 등, /seed)")

    cross_implications: List[CrossImplication] = Field(
        default_factory=list, description="★ S2 도메인 횡단 '참고' 시사점 (근거·근접도 인용)"
    )
    design_drivers: List[DesignDriver] = Field(
        default_factory=list, description="★ T2 지배 설계 드라이버 2~3개 (증거강도 랭킹·검토 신호)"
    )
    program_implications: List[ProgramItem] = Field(
        default_factory=list, description="★ T3 프로그램 함의(POR) — 카테고리별 공간·프로그램 권고"
    )
    coverage: List[DomainCoverage] = Field(
        default_factory=list, description="도메인별 데이터 확보 여부 (no silent skip)"
    )
    synthesis: Optional[Synthesis] = Field(
        None, description="★ S4 종합 산출 두 블록 (synthesize=true일 때만). ①사실 해석 + ②AI 판단"
    )
    base_date: str = Field(..., description="기준일 YYYY-MM-DD", examples=["2026-07-09"])
    notes: List[str] = Field(
        default_factory=list, description="투명성 메모 (미확정·확인불가·부분실패 병합)"
    )
