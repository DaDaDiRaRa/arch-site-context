"""생성물 이력 — GET /history(목록) · GET /history/{id}/file(재다운로드).

만든 PPT(대지분석 덱·종합읽기)를 버리지 않고 목록으로 보관 → 재생성 없이 다시 받기.
저장·백엔드(GCS/로컬)는 services.history 담당. 여기선 노출만.
"""

from __future__ import annotations

import io

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from app.services import history

router = APIRouter(tags=["history"])

_MEDIA = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


@router.get("/history")
def history_list() -> dict:
    """생성 이력 목록 (최신순). 각 항목: id·kind·title·params·created·size·backend."""
    return {"items": history.list_entries()}


@router.get("/history/{gid}/file")
def history_file(gid: str):
    """이력 1건 재다운로드 (pptx 스트리밍). 파일명은 프론트가 title 로 지정."""
    r = history.read(gid)
    if not r:
        return JSONResponse(status_code=404, content={"detail": "이력을 찾을 수 없습니다 (만료·삭제됨)."})
    data, _fn = r
    return StreamingResponse(
        io.BytesIO(data), media_type=_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="download.pptx"'},
    )
