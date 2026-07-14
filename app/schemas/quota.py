"""C2 — 주민공동시설 총량제 산정 스키마 (CLAUDE.md §8.13 심의 현황팩).

서울시 통합심의 '커뮤니티 설치계획(총량제) 검토' 박스를 재현한다.
값은 코드 산수, 규칙(tier·계수)은 community_quota.json (절대 원칙 2·7).

⚠ 법정 최소면적은 조례 개정·자치구·연도에 따라 변동값 — tier 마다 confidence 를 실어
"이 값이 얼마나 확실한가"를 투명하게 (절대 원칙 4). 산출 공식(예상인원 방식)은 안정적이나
법정면적은 신규 프로젝트마다 조례 확인이 필요. 판정은 '참고' — 최종 확정은 사람 (절대 원칙 5).
"""

from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

from app.schemas.survey import FacilityCategory, SurveyResult

Confidence = Literal["high", "med", "low"]


class FacilityQuota(BaseModel):
    """시설 1개의 총량제 산정 결과."""

    name: str = Field(..., description="시설명", examples=["작은도서관"])
    households: int = Field(..., description="산정에 쓴 세대수 (신축+조사범위 또는 조사범위)")
    expected_people: Optional[float] = Field(
        None, description="예상인원 (도서관·어린이집만; 경로당은 세대 선형이라 없음)"
    )
    required_area: Optional[float] = Field(
        None, description="심의검토 산출면적(㎡) = 예상×면적 − 기존시설. >0 이면 부족"
    )
    existing_area: float = Field(0.0, description="조사범위 내 기존 시설 총면적(㎡) — 조사입력")
    planned_area: Optional[float] = Field(None, description="계획면적(㎡) — 설계입력")
    legal_min: Optional[float] = Field(
        None, description="법정 최소면적(㎡). tier·formula 로 산정. None=미확정/필수아님"
    )
    legal_min_confidence: Optional[Confidence] = Field(
        None, description="법정면적 tier 확신도 (조례 변동성) — low 면 조례 확인 필요"
    )
    verdict: Optional[str] = Field(
        None, description="부족시설|충족시설|면적기준|확인필요 ('참고')"
    )
    plan_ok: Optional[bool] = Field(None, description="계획면적 ≥ 법정면적 여부")
    plan_diff: Optional[float] = Field(None, description="계획 − 법정 (㎡)")
    notes: List[str] = Field(default_factory=list, description="정직한 메모 (조례 변동·미확정 등)")
    tag: str = Field("참고", examples=["참고"])


class QuotaResult(BaseModel):
    """한 획지(또는 단지)의 총량제 검토 결과."""

    label: str = Field("", description="획지 라벨 (다획지 구분용)", examples=["획지1"])
    new_households: int = Field(..., description="신축 세대수 (설계입력) — tier 선택 기준")
    applied_households: int = Field(..., description="조사범위 걸침 적용세대 (C1)")
    facilities: List[FacilityQuota] = Field(..., description="시설별 산정")
    total_quota_area: Optional[float] = Field(
        None, description="주민공동시설 합계 총량(㎡) — 참고"
    )
    notes: List[str] = Field(default_factory=list)


class ContextPackRequest(BaseModel):
    """POST /context-pack 입력 — 심의 커뮤니티 총량제 검토."""

    address: str = Field(..., description="대지 주소", examples=["서울특별시 동작구 본동 441"])
    new_households: Union[int, List[int]] = Field(
        ..., description="신축 세대수(설계입력). 다획지면 리스트 [획지1, 획지2]", examples=[981, [409, 581]]
    )
    radius: int = Field(1000, description="조사범위 반경(m)", examples=[1000])
    ym: Optional[str] = Field(None, description="인구·세대 기준 년월 YYYYMM (없으면 최신)")
    existing_area: Optional[dict] = Field(
        None, description="조사범위 기존 시설 총면적 {시설명:㎡} (조사입력)")
    planned_area: Optional[dict] = Field(
        None, description="계획면적 {시설명:㎡} (설계입력)")
    labels: Optional[List[str]] = Field(None, description="획지 라벨")


class QuotaAssessment(BaseModel):
    """주소 1건의 총량제 종합 (C1 걸침 + 구 영유아/세대 + C2 판정). /context-pack 진입점."""

    address: str
    site_sgg: str = Field("", description="대지 시군구코드")
    site_lat: float = Field(0.0, description="대지 위도 (위치도용)")
    site_lon: float = Field(0.0, description="대지 경도")
    radius: int = Field(1000)
    ym: str = Field("", description="인구·세대 기준 년월")
    gu_infant: Optional[int] = Field(None, description="구 영유아(0-4세) 인구 — KOSIS")
    gu_households: Optional[int] = Field(None, description="구 세대 — 행안부 rdoa 동 합산")
    survey: SurveyResult = Field(..., description="조사범위 걸침 합산 (C1)")
    facilities: List[FacilityCategory] = Field(
        default_factory=list, description="조사범위 내 시설 현황 (도서관·경로당·어린이집 목록·개수)")
    results: List[QuotaResult] = Field(..., description="획지별 총량제 판정 (C2)")
    notes: List[str] = Field(default_factory=list)
