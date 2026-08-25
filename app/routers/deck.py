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


@router.post("/deck/svg")
def deck_svg(req: DeckRequest):
    """지도 4종(광역·용도·높이·조망)의 **독립 SVG 산출물**(zip) — `map_slides.py` PPTX 네이티브
    트랙은 그대로 두고, 같은 데이터에서 SVG를 하나 더 뽑는 별도 출력(§8.15). 도형마다
    `id`·`data-source-ref`를 심어 근거 추적 가능(semantic-svg는 위성배경·건물폴리곤·조망호를
    표현 못 해 평가 후 배제 — 직접 SVG 생성으로 대체, `app/deck/map_svg.py` 참조).
    """
    import zipfile

    from app.deck.map_svg import build_map_svgs
    try:
        svgs = build_map_svgs(req.address, req.use_type, req.radius)
    except ValueError as e:  # 주소 해석 실패 — 추정 대신 명확히 멈춤 (절대 원칙 3)
        return JSONResponse(status_code=422, content={"detail": str(e)})
    if not svgs:
        return JSONResponse(status_code=422, content={"detail": "지도 생성 실패 — 위성지도·건물모델 확인 필요"})
    names = {"wide": "광역입지도", "use": "건물용도현황", "site": "입지현황", "viewring": "조망분석"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, svg in svgs.items():
            zf.writestr(f"{names.get(key, key)}.svg", svg)
    data = buf.getvalue()
    try:
        from app.services import history
        history.save("deck_svg", req.address, {"use_type": req.use_type, "radius": req.radius},
                     f"대지분석지도_{req.address.replace(' ', '')}.zip", data)
    except Exception:  # noqa: BLE001
        pass
    return StreamingResponse(
        io.BytesIO(data), media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="site_maps_svg.zip"'},
    )


@router.post("/deck/dxf")
def deck_dxf(req: DeckRequest):
    """**통합 CAD 대지계획도**(.dxf) — SVG(`/deck/svg`) 다음 산출물(§8.15). 슬라이드별로 쪼개지
    않고 AutoCAD·Civil3D·Rhino에 바로 불러 쓸 수 있는 site plan 한 장으로 통합(2026-08-25
    사용자 결정) — SITE 경계·건물 평면(용도별 레이어)·반경 참조원·방위. 좌표는 실제 미터
    단위(대지=원점). `app/deck/site_dxf.py` 참조.
    """
    from app.deck.site_dxf import build_site_dxf
    try:
        data = build_site_dxf(req.address, req.use_type, req.radius)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    try:
        from app.services import history
        history.save("deck_dxf", req.address, {"use_type": req.use_type, "radius": req.radius},
                     f"대지계획도_{req.address.replace(' ', '')}.dxf", data)
    except Exception:  # noqa: BLE001
        pass
    return StreamingResponse(
        io.BytesIO(data), media_type="application/dxf",
        headers={"Content-Disposition": 'attachment; filename="site_plan.dxf"'},
    )


@router.post("/deck/glb")
def deck_glb(req: DeckRequest):
    """건물 매싱 **GLB(3D)** — SVG·DXF 다음 산출물(§8.15). arch-site-model 은 glb 를 지원하지
    않아(직접 소스 확인, 2026-08-25) 우리가 footprint+height 를 직접 박스압출해 생성한다.
    `app/deck/site_glb.py` 참조.
    """
    from app.deck.site_glb import build_site_glb
    try:
        data = build_site_glb(req.address)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    try:
        from app.services import history
        history.save("deck_glb", req.address, {"use_type": req.use_type, "radius": req.radius},
                     f"건물매싱_{req.address.replace(' ', '')}.glb", data)
    except Exception:  # noqa: BLE001
        pass
    return StreamingResponse(
        io.BytesIO(data), media_type="model/gltf-binary",
        headers={"Content-Disposition": 'attachment; filename="site_massing.glb"'},
    )
