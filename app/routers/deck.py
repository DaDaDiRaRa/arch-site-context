"""대지분석 덱 — POST /deck/full (deck-builder 흡수, 구 별도 서비스).

지도 4종(광역·용도·높이·조망) + 데이터(지역통계·수급진단·대지정보·생활맥락·주변현황도·주변시설)
+ 시설 종류별 상세를 한 PPTX 로 조립. 터읽기 내부 데이터는 직접 호출(자기 HTTP 회피),
model·law 만 형제앱 HTTP(env). 프론트 L탭이 호출. 전부 graceful — 소스 하나 죽어도 나머지로.
"""

from __future__ import annotations

import io

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(tags=["deck"])


class DeckRequest(BaseModel):
    address: str = Field(..., description="대지 주소", examples=["서울특별시 영등포구 당산동3가 385"])
    use_type: str = Field("주거", description="건물 용도 — matrix.json 키")
    radius: int = Field(1000, ge=100, le=5000, description="시설·상권 반경(m)")


@router.post("/deck/full")
def deck_full(req: DeckRequest):
    """종합 대지분석 덱 A3 편집가능 PPTX 다운로드."""
    from app.deck.map_slides import build_full_deck
    try:
        data = build_full_deck(req.address, req.use_type, req.radius)
    except ValueError as e:  # 주소 해석 실패 등 — 추정 대신 명확히 멈춤 (절대 원칙 3)
        return JSONResponse(status_code=422, content={"detail": str(e)})
    # 생성 이력 저장 (best-effort — 실패해도 다운로드는 진행)
    try:
        from app.services import history
        history.save("deck", req.address, {"use_type": req.use_type, "radius": req.radius},
                     f"대지분석_{req.address.replace(' ', '')}.pptx", data)
    except Exception:  # noqa: BLE001
        pass
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": 'attachment; filename="site_deck.pptx"'},
    )
