"""대지분석 덱 — POST /deck/full (deck-builder 흡수, 구 별도 서비스).

지도 4종(광역·용도·높이·조망) + 데이터(지역통계·수급진단·대지정보·생활맥락·주변현황도·주변시설)
+ 시설 종류별 상세를 한 PPTX 로 조립. 터읽기 내부 데이터는 직접 호출(자기 HTTP 회피),
model·law 만 형제앱 HTTP(env). 프론트 L탭이 호출. 전부 graceful — 소스 하나 죽어도 나머지로.
"""

from __future__ import annotations

import io

from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.deck.style import DEFAULT_PLAN_RADIUS_M

router = APIRouter(tags=["deck"])


class DeckRequest(BaseModel):
    address: str = Field(..., description="대지 주소", examples=["서울특별시 영등포구 당산동3가 385"])
    use_type: str = Field("주거", description="건물 용도 — matrix.json 키")
    radius: int = Field(1000, ge=100, le=5000, description="시설·상권 **데이터** 반경(m)")
    plan_radius: Optional[int] = Field(
        None, ge=10, le=2000,
        description="CAD·3D **도면 범위**(m). /deck/dxf·/deck/glb 전용 — 건물 매싱을 받아올 반경. "
                    "미지정이면 350m. 상한 2000 은 arch-site-model /api/generate 계약과 같다.",
    )

    @property
    def plan_radius_m(self) -> int:
        """도면 반경 — 미지정이면 기본값. `radius`(데이터 반경)와 다른 축이라 섞지 않는다."""
        return self.plan_radius or DEFAULT_PLAN_RADIUS_M


class RenderRequest(BaseModel):
    """`deck_render/1.0` — **밖에서 준 내용**을 우리 스타일로 그린다.

    첫 사용처는 컨셉 스튜디오(`:8200`)의 컨셉 장표다. 그 앱이 「무엇을 적을 것인가」를
    알고 우리가 「어떻게 그릴 것인가」를 안다 — **우리는 「컨셉」이 무엇인지 모른다.**
    받는 낱말은 `cover`·`kpi`·`cards`·`table`·`text` 다섯뿐이고 전부 이미 우리 어휘다.

    여기에 도메인 분기를 넣기 시작하면 deck-builder 가 접힌 이유를 되풀이한다.
    """

    schema_version: str = Field("deck_render/1.0")
    title: str = Field(..., description="덱 제목 — 파일 이름과 표지에 쓴다")
    subtitle: str = ""
    filename: str = Field("deck.pptx", description="내려받을 이름")
    slides: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/deck/render")
def deck_render(req: RenderRequest):
    """슬라이드 목록 → A3 편집가능 PPTX. 데이터를 우리가 모으지 않는 유일한 덱 엔드포인트."""
    from app.deck.render_slides import build
    try:
        data = build(req.model_dump())
    except ValueError as e:      # 빈 목록 등 — 추정 대신 명확히 멈춘다 (절대 원칙 3)
        return JSONResponse(status_code=422, content={"detail": str(e)})
    name = (req.filename or "deck.pptx").replace('"', "")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


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
        svgs = build_map_svgs(req.address)
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
        history.save("deck_svg", req.address, {"scales": "광역2km·용도/높이320m·조망600m"},
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
        data = build_site_dxf(req.address, req.use_type, req.plan_radius_m)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    try:
        from app.services import history
        history.save("deck_dxf", req.address, {"use_type": req.use_type, "plan_radius": req.plan_radius_m},
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
        data = build_site_glb(req.address, req.plan_radius_m)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    try:
        from app.services import history
        history.save("deck_glb", req.address, {"plan_radius": req.plan_radius_m},
                     f"건물매싱_{req.address.replace(' ', '')}.glb", data)
    except Exception:  # noqa: BLE001
        pass
    return StreamingResponse(
        io.BytesIO(data), media_type="model/gltf-binary",
        headers={"Content-Disposition": 'attachment; filename="site_massing.glb"'},
    )
