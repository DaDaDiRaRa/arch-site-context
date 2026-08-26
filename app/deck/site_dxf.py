"""통합 CAD 대지계획도 — 지도 4종 SVG(§8.15 첫 항목, `map_svg.py`)에 이은 DXF 산출물.

`map_slides.py`(PPTX 4장)·`map_svg.py`(SVG 4장)처럼 슬라이드/다이어그램별로 쪼개지 않고,
건축가가 AutoCAD·Civil3D·Rhino에 바로 불러 쓸 수 있는 **하나의 site plan .dxf**로
통합한다(2026-08-25 사용자 결정) — 위성사진·범례패널·캡션밴드는 CAD 도면에 의미가 없어
제외하고, SITE 경계·건물 평면(용도별 레이어)·반경 참조원·방위만 담는다.

좌표는 **실제 미터 단위**(대지를 원점(0,0)으로 하는 로컬 좌표계) — 축척 1:1로 바로 쓸 수
있다. arch-site-model의 건물 footprint(그 앱 자체 origin_offset 기준)는 위경도로
왕복 변환해 우리 대지-원점 좌표계로 재투영한다(모델의 임의 원점에 기대지 않음).
"""
from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import ezdxf

from app.deck import clients
from app.deck import map_slides as ms
import app.deck.style as k

#: 용도별 레이어 색(ACI, AutoCAD Color Index)
_LAYER_COLOR = {"주거": 5, "상업": 30, "업무": 4, "공업": 8, "공공": 3, "미상": 9}
#: 도면 기본 반경 — deck 공용(style)에서. dxf·glb·라우터가 같은 값을 본다.
DEFAULT_PLAN_RADIUS_M = k.DEFAULT_PLAN_RADIUS_M
#: 참조원이 고를 수 있는 '읽기 좋은' 반경 사다리 — 도면 반경에 맞춰 3개를 뽑는다.
_REF_LADDER = (25, 50, 100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000)


def _ref_radii(plan_radius: int) -> tuple:
    """참조원 3개 = (≈⅓, ≈⅔, 도면 반경). 안쪽 둘은 사다리에서 가장 가까운 값으로 반올림.

    반경이 바뀌면 참조원도 따라가야 한다 — 예전엔 (100,200,350) 고정이라 도면 반경과
    어긋날 수 있었다. 350m 기준으로는 (100, 250, 350).
    """
    def nearest(target):
        return min(_REF_LADDER, key=lambda v: abs(v - target))
    return tuple(sorted({nearest(plan_radius / 3), nearest(plan_radius * 2 / 3), int(plan_radius)}))


def _classified_buildings(model, fac, my_ox, my_oy):
    """model 건물 footprint → 대지-원점 로컬미터 좌표 + 용도분류(map_slides.slide_use 와 같은
    근접매칭 로직, 캔버스/픽셀 의존 없이 실좌표로만)."""
    model_ox, model_oy = (model.get("stats") or {})["origin_offset"]
    strong, weak = [], []
    for f in (fac or {}).get("results", []):
        u = ms.KIND_USE.get(f.get("kind"))
        nm = str(f.get("name") or "")
        if u and f.get("lat") is not None:
            is_strong = f.get("kind") in ms._USE_STRONG
            if f.get("kind") == "병원" and any(w in nm for w in ("의원", "치과", "한의원", "동물")):
                is_strong = False
            (strong if is_strong else weak).append((f["lat"], f["lon"], u, nm))

    out = []
    for b in (model.get("geometry") or {}).get("buildings") or []:
        fp = b.get("footprint") or []
        if len(fp) < 3:
            continue
        fp_latlon = [k.local_to_latlon(px, py, model_ox, model_oy) for px, py in fp]
        clat = sum(p[0] for p in fp_latlon) / len(fp_latlon)
        clon = sum(p[1] for p in fp_latlon) / len(fp_latlon)

        def nearest(lst):
            bd, bu, bn = 1e9, None, None
            for (pla, plo, pu, pn) in lst:
                d = clients._haversine_m(clat, clon, pla, plo)
                if d < bd:
                    bd, bu, bn = d, pu, pn
            return bd, bu, bn
        sd, su, sn = nearest(strong)
        wd, wu, wn = nearest(weak)
        if sd < 45:
            use, nm = su, sn
        elif wd < 35:
            use, nm = wu, wn
        else:
            use, nm = "미상", None
        nu = ms._name_use(nm) if nm else None
        pts_site = [k.latlon_to_local(plat, plon, my_ox, my_oy) for plat, plon in fp_latlon]
        out.append({"pts": pts_site, "h": b.get("height") or 0.0, "use": nu or use,
                    "name": nm if (nm and ms._name_use(nm)) else None})
    return out


def build_site_dxf(address: str, use_type: str = "주거",
                   model_radius_m: int = DEFAULT_PLAN_RADIUS_M) -> bytes:
    """주소 → 통합 CAD 대지계획도(.dxf, 실미터 좌표, 대지=원점). 건물모델 없으면 SITE·반경원·방위만.

    `model_radius_m` = **도면 범위**(건물 매싱을 받아올 반경). `/deck/full` 의 `radius`(시설·상권
    데이터 반경)와는 다른 축이라 따로 받는다 — 200m 근경이냐 500m 블록 스터디냐는 도면 쪽 선택.
    참조원·방위·표제 위치가 전부 여기서 파생된다. 상한은 arch-site-model `/api/generate` 계약(2000m).
    """
    from app.services.site_seed import build_site
    try:
        s = build_site(address)
        lat, lon = s.lat, s.lon
        pnu = s.pnu or ""
    except Exception:  # noqa: BLE001 — 주소 해석 실패는 하드블록
        raise ValueError("주소 해석 실패")
    if lat is None:
        raise ValueError("주소 해석 실패")

    ref_radii = _ref_radii(model_radius_m)
    # 용도분류용 시설검색은 도면 안쪽만 보면 된다(건물 중심에서 45m 내 매칭) — 반경에 비례.
    fac_radius = max(100, int(model_radius_m * 0.92))
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_model = ex.submit(clients.fetch_model, address, model_radius_m)
        f_law = ex.submit(clients.fetch_law, address, pnu)
        f_fac = ex.submit(clients.fetch_facilities, address, list(ms.KIND_USE.keys()), fac_radius)
        model, law, fac = f_model.result(), f_law.result(), f_fac.result()

    my_ox, my_oy = k.latlon_to_local(lat, lon, 0.0, 0.0)  # 대지 자신의 EPSG:5186 좌표 = 우리 도면 원점

    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.M
    for name, color in [("SITE", 1), ("REF-RADIUS", 8), ("ANNOTATION", 7)]:
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    for use, color in _LAYER_COLOR.items():
        doc.layers.add(f"BLDG-{use}", color=color)
    msp = doc.modelspace()

    for rm in ref_radii:
        msp.add_circle((0, 0), rm, dxfattribs={"layer": "REF-RADIUS"})
        msp.add_text(f"{rm}m", dxfattribs={"layer": "REF-RADIUS", "height": 3.0}).set_placement((0, rm + 1))

    ring = k.parcel_ring((law or {}).get("parcel_geometry"))
    parcel_pts = [k.latlon_to_local(pt[1], pt[0], my_ox, my_oy) for pt in ring]
    if len(parcel_pts) >= 3:
        msp.add_lwpolyline(parcel_pts, close=True, dxfattribs={"layer": "SITE"})
    msp.add_circle((0, 0), 2.0, dxfattribs={"layer": "SITE"})
    msp.add_text("SITE", dxfattribs={"layer": "SITE", "height": 3.0}).set_placement((3.0, 0))

    n_count = 0
    if model:
        try:
            blds = _classified_buildings(model, fac, my_ox, my_oy)
            for b in blds:
                layer = f"BLDG-{b['use']}"
                msp.add_lwpolyline(b["pts"], close=True, dxfattribs={"layer": layer})
                cx = sum(p[0] for p in b["pts"]) / len(b["pts"])
                cy = sum(p[1] for p in b["pts"]) / len(b["pts"])
                label = b["name"] or b["use"]
                msp.add_text(f"{label} {int(b['h'])}m",
                            dxfattribs={"layer": layer, "height": 2.2}).set_placement((cx, cy))
            n_count = len(blds)
        except Exception:  # noqa: BLE001 — 건물 매싱 실패해도 SITE·반경원·방위는 남긴다
            pass

    # 방위(N) — 화살표 + 라벨
    ny0 = max(ref_radii) + 20
    msp.add_line((0, ny0), (0, ny0 + 12), dxfattribs={"layer": "ANNOTATION"})
    msp.add_lwpolyline([(-2, ny0 + 9), (0, ny0 + 12), (2, ny0 + 9)], dxfattribs={"layer": "ANNOTATION"})
    msp.add_text("N", dxfattribs={"layer": "ANNOTATION", "height": 4.0}).set_placement((3, ny0 + 6))

    # 표제 텍스트
    ty0 = -(max(ref_radii) + 15)
    msp.add_text(f"터읽기 대지계획도 CAD 베이스 · {address}",
                dxfattribs={"layer": "ANNOTATION", "height": 3.0}).set_placement((-60, ty0))
    msp.add_text(f"용도 {use_type} · 도면반경 {model_radius_m}m · 건물 {n_count}동 · "
                f"생성 {datetime.now():%Y-%m-%d} · "
                f"출처: VWorld·카카오·arch-site-model(§2 원칙4)",
                dxfattribs={"layer": "ANNOTATION", "height": 2.2}).set_placement((-60, ty0 - 5))

    buf = io.StringIO()
    doc.write(buf)
    return doc.encode(buf.getvalue())
