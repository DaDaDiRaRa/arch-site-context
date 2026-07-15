"""GET /matrix — 용도별 KOSIS 항목 목록 (투명성).

matrix.json 을 use_type·min_priority 로 걸러 반환. 건축가가 코드 없이 JSON만 수정 (절대 원칙 7).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.matrix import (
    data_limited_uses,
    legal_uses,
    list_items,
    resolve_profile,
    use_type_groups,
    use_types,
)

router = APIRouter(tags=["mode-a"])


@router.get("/matrix")
def matrix(
    use_type: Optional[str] = Query(None, description="용도 — 분석 프로파일(주거/상업/의료/복합/공공/교육/복지) 또는 법적 용도(공동주택 등). 미지정 시 전체"),
    min_priority: int = Query(3, ge=1, le=3, description="이 값 이하 우선순위(1=필수)만"),
) -> dict:
    """용도별 항목 목록 반환 (투명성). 법적 용도면 프로파일로 해석. 모르는 용도면 404."""
    if use_type is not None:
        items = list_items(use_type, min_priority)
        if items is None:
            raise HTTPException(
                status_code=404,
                detail=f"알 수 없는 용도: {use_type} (사용 가능: {', '.join(use_types())})",
            )
        # 법적 용도 입력 시 해석된 프로파일도 투명하게 노출
        return {"use_type": use_type, "profile": resolve_profile(use_type),
                "min_priority": min_priority, "items": items}
    return {
        "use_types": use_types(),
        "min_priority": min_priority,
        "matrix": list_items(None, min_priority),
    }


@router.get("/use-types")
def use_type_catalog() -> dict:
    """2계층 용도 카탈로그 — 프론트 드롭다운용.

    profiles(분석 프로파일) · groups(법적 용도 그룹핑) · map(법적→프로파일) ·
    data_limited(인구통계로 차별화 못 하는 용도 — 캐비엇 표시 대상).
    """
    return {
        "profiles": use_types(),
        "groups": use_type_groups(),
        "map": {u: resolve_profile(u) for u in legal_uses()},
        "data_limited": data_limited_uses(),
    }
