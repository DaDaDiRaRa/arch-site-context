"""모드 B — 주변 시설 스키마.

출처: CLAUDE.md 6장 데이터 계약. 좌표·거리·집계는 코드만 할 수 있는 계산이며
값은 실제 API(카카오)에서 호출해 가져온다 (절대 원칙 1).
"""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field

# 반경 밴드는 "500"·"1000"·"2000"처럼 미터값의 문자열. radii 입력에 따라 가변.
RadiusBand = str

DEFAULT_KINDS = ["어린이집", "경로당"]
DEFAULT_RADII = [500, 1000, 2000]


class FacilityRequest(BaseModel):
    """POST /facilities 입력."""

    address: str = Field(..., description="대지 주소", examples=["서울 영등포구 여의대로 24"])
    kinds: List[str] = Field(
        default_factory=lambda: list(DEFAULT_KINDS),
        description="찾을 시설종류 목록 (빈 목록이면 기본 세트로 대체)",
        examples=[["어린이집", "경로당"]],
    )
    radii: List[int] = Field(
        default_factory=lambda: list(DEFAULT_RADII),
        description="반경 밴드(m) 오름차순. 가장 큰 값이 카카오 검색 반경.",
        examples=[[500, 1000, 2000]],
    )


class MapRequest(FacilityRequest):
    """POST /facilities/map 입력. 시설 요청과 동일 + 배경지도 선택."""

    basemap: str = Field(
        "vworld", description="배경지도: 'vworld'(위성) | 'kakao'(스카이뷰, 미구현)"
    )


class Facility(BaseModel):
    """반경 내 시설 1건."""

    kind: str = Field(..., examples=["어린이집"])
    name: str = Field(..., examples=["여의도어린이집"])
    lat: float = Field(..., examples=[37.5219])
    lon: float = Field(..., examples=[126.9245])
    dist_m: int = Field(..., description="중심(대지)으로부터 하버사인 거리(m)", examples=[420])
    radius_band: RadiusBand = Field(..., description="이 시설이 속한 가장 작은 반경 밴드(m)")
    src: str = Field("kakao", description="데이터 출처 (kakao|osm|gov)", examples=["kakao"])


class Center(BaseModel):
    """검색 중심(대지) 좌표."""

    lat: float = Field(..., examples=[37.5260])
    lon: float = Field(..., examples=[126.9265])
    address: str = Field(..., examples=["서울 영등포구 여의대로 24"])


class FacilityResult(BaseModel):
    """POST /facilities 출력 (모드 B)."""

    center: Center
    results: List[Facility]
    counts: Dict[str, Dict[str, int]] = Field(
        ..., description="반경밴드(누적)별 시설종류별 개수"
    )
    source: str = Field("kakao", description="데이터 출처 (출처 명시 — 절대 원칙 4)")
    base_date: str = Field(..., description="기준일 YYYY-MM-DD", examples=["2026-06-25"])
    notes: List[str] = Field(
        default_factory=list,
        description="커버리지 경고 등 정직한 메모 (예: 일부 영역 카카오 상한 도달). no silent cap.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "center": {
                        "lat": 37.5260,
                        "lon": 126.9265,
                        "address": "서울 영등포구 여의대로 24",
                    },
                    "results": [
                        {
                            "kind": "어린이집",
                            "name": "여의도어린이집",
                            "lat": 37.5219,
                            "lon": 126.9245,
                            "dist_m": 420,
                            "radius_band": "500",
                        }
                    ],
                    "counts": {
                        "500": {"어린이집": 3, "경로당": 5},
                        "1000": {"어린이집": 7, "경로당": 12},
                        "2000": {"어린이집": 18, "경로당": 30},
                    },
                    "source": "kakao",
                    "base_date": "2026-06-25",
                }
            ]
        }
    }
