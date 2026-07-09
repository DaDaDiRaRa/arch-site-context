"""arch-site-model 결합 스키마 — 물리 3D 레이어의 압축 요약 (INTEGRATION.md §4).

터읽기는 **provider**로서 arch-site-model 을 호출하지 않는다. assembler(competition·kw-ai-hub·
Claude)가 넘긴 arch-site-model 출력을 받아 **렌더·요약만** 한다 (경계 유지).

arch-site-model 이 스키마의 주인이므로(project_seed 의 law·knowledge 처럼) 원시 출력은 느슨한
dict 로 받고, 여기서는 **보드 렌더·패널에 필요한 것만 압축 투영**한다 — 새 숫자 0, 값은 arch-site-model
이 만든 그대로 (절대 원칙 1·2). 원시 geometry(터레인 수천 삼각형)는 담지 않고 건물 footprint 만.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

# 미리보기 렌더용 건물 상한 (응답 비대화 방지 — 초과분은 note)
MAX_FOOTPRINTS = 400


class SiteModelSummary(BaseModel):
    """arch-site-model 물리 모델의 압축 요약 (렌더·패널용). 원시 스키마는 arch-site-model 소유."""

    source: str = Field("arch-site-model", description="출처 앱")
    schema_version: str = Field("site_model/1.0", description="이 투영 버전 (arch-site-model 원시 계약과 별개)")

    building_count: Optional[int] = Field(None, description="조회된 건물 수 (stats.buildings)", examples=[42])
    solids: Optional[int] = Field(None, description="생성된 솔리드 수 (stats.solids)", examples=[42])
    cadastral_parcels: Optional[int] = Field(None, description="필지 수 (stats.cadastral_parcels)", examples=[12])
    elev_range_m: Optional[List[float]] = Field(None, description="DEM 표고 범위 [min,max] (stats.elev_range_m)", examples=[[35.2, 112.7]])
    origin_offset: Optional[List[float]] = Field(
        None, description="EPSG:5186 씬 로컬 원점 [ox,oy] — 좌표 복원용 (stats.origin_offset)", examples=[[936142.5, 415678.2]]
    )
    radius_m: Optional[int] = Field(None, description="모델 생성 반경(m)", examples=[250])

    footprints: List[List[List[float]]] = Field(
        default_factory=list,
        description="건물 외곽선 목록 (로컬 미터, 미리보기용). 각 building = [[x,y],...]. MAX_FOOTPRINTS 상한",
    )
    heights_m: List[float] = Field(
        default_factory=list, description="footprints 와 평행한 건물 높이(m)"
    )

    files: dict = Field(default_factory=dict, description="다운로드 URL {'3dm':..,'ortho':..} (arch-site-model 서빙)")
    provenance: dict = Field(default_factory=dict, description="원시 provenance (building_src·radius_m·fetched_at 등)")
    warnings: List[str] = Field(default_factory=list, description="arch-site-model 경고 (층수 누락 등)")
    note: str = Field("", description="주의 (상한 절삭·요약 등)")
