"""GET /matrix — 용도별 KOSIS 항목 목록 (투명성).

matrix.json 을 use_type·min_priority 로 걸러 반환. 건축가가 코드 없이 JSON만 수정 (절대 원칙 7).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.matrix import list_items, use_types

router = APIRouter(tags=["mode-a"])


@router.get("/matrix")
def matrix(
    use_type: Optional[str] = Query(None, description="용도 (예: 주거/상업/의료). 미지정 시 전체"),
    min_priority: int = Query(3, ge=1, le=3, description="이 값 이하 우선순위(1=필수)만"),
) -> dict:
    """용도별 항목 목록 반환 (투명성). 모르는 용도면 404."""
    if use_type is not None:
        items = list_items(use_type, min_priority)
        if items is None:
            raise HTTPException(
                status_code=404,
                detail=f"알 수 없는 용도: {use_type} (사용 가능: {', '.join(use_types())})",
            )
        return {"use_type": use_type, "min_priority": min_priority, "items": items}
    return {
        "use_types": use_types(),
        "min_priority": min_priority,
        "matrix": list_items(None, min_priority),
    }
