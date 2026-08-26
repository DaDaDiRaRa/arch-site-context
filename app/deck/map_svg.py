"""대지분석 지도 4종의 독립 SVG 출력 (§8.15 두번째 항목).

`map_slides.py`의 PPTX 네이티브 편집가능 트랙은 그대로 둔다 — 이 모듈은 **같은 데이터·
같은 계산**(건물 매싱·용도분류·조망섹터)에서 SVG 산출물을 하나 더 만드는 것이지 PPTX를
대체하지 않는다.

★ semantic-svg(AlexAI-MCP) 평가 결과(2026-08-25) — 도입하지 않음: 그 컴파일러는 지식그래프
전용(노드=원, 엣지=곡선 path, 좌표는 0~1 정규화, 배경이미지·임의폴리곤·호(arc)·좌표계 변환
전부 미지원)이라 "위성 배경 + 건물 폴리곤 + 방향별 호"로 구성된 이 지도들을 표현할 수 없다.
대신 **직접 SVG 생성 + 자체 provenance 규약**을 쓴다 — 데이터에 묶인 도형마다 안정적인
`id`와 `data-source-ref`(어느 API·필드에서 왔는지)를 심어, semantic-svg가 하려던 "도형을
누르면 근거가 따라온다"는 목표를 우리 스택 안에서 직접 구현한다. 상세: 메모리
`svg-diagram-track`.
"""
from __future__ import annotations

import base64
import io
import math
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from lxml import etree
from PIL import Image

from app.deck import clients
from app.deck import map_slides as ms
import app.deck.style as k

NS = "http://www.w3.org/2000/svg"

NAVY, RED, WHITE, MUTE, INK, GRAY = (
    "#1B2438", "#E1242B", "#FFFFFF", "#B4BFD2", "#1E1E1E", "#555555",
)

# ── 레이아웃 상수 (지도 캔버스 + 우측 패널 + 하단 캡션밴드) ──
MAP = 1500
GAP = 32
PANEL_W = 480
HEADER_H = 120
CAPTION_H = 130
MAP_X, MAP_Y = GAP, HEADER_H
PANEL_X = MAP_X + MAP + GAP
TOTAL_W = PANEL_X + PANEL_W + GAP
TOTAL_H = HEADER_H + MAP + CAPTION_H


def _hex(c) -> str:
    """pptx RGBColor → '#RRGGBB' (map_slides.py·style.py 색 토큰 재사용)."""
    return f"#{c}"


HL_HEX = _hex(ms.HL)


# ── SVG 저수준 빌더 ──
def _el(parent, tag, attrib=None, text=None):
    e = etree.SubElement(parent, f"{{{NS}}}{tag}",
                          attrib={kk: str(v) for kk, v in (attrib or {}).items() if v is not None})
    if text is not None:
        e.text = str(text)
    return e


def _svg_root():
    return etree.Element(f"{{{NS}}}svg", nsmap={None: NS}, attrib={
        "viewBox": f"0 0 {TOTAL_W} {TOTAL_H}", "width": str(TOTAL_W), "height": str(TOTAL_H),
        "font-family": "'Malgun Gothic','맑은 고딕',sans-serif",
    })


def _serialize(root) -> str:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8").decode("utf-8")


def _page(title, subtitle):
    root = _svg_root()
    _el(root, "rect", {"x": 0, "y": 0, "width": TOTAL_W, "height": TOTAL_H, "fill": NAVY})
    _el(root, "text", {"x": GAP, "y": 50, "font-size": 34, "fill": WHITE, "font-weight": "bold"}, f"[ {title} ]")
    if subtitle:
        _el(root, "text", {"x": GAP, "y": 80, "font-size": 15, "fill": MUTE}, subtitle)
    return root, MAP_X, MAP_Y


def _image(root, png, x, y, w, h, *, id_=None, source_ref=None):
    """위성 PNG를 SVG에 base64 임베드. 실측(2026-08-25) — 원본 PNG(무손실)를 그대로 넣으면
    1500x1500 기준 장당 ~4.5MB → base64 텍스트라 zip 압축도 잘 안 먹어(파일당 ~12MB).
    사진(위성영상)은 무손실일 필요가 없으므로 **JPEG로 재인코딩**(품질 87 — 실측 ~880KB,
    5배 이상 축소) 후 임베드. `xlink:href` 중복은 안 넣는다 — SVG2 `href` 하나만으로도
    이미지 바이트가 그대로 두 번 들어가는 걸 막는다(예전엔 호환성 명목으로 둘 다 넣어
    파일 크기가 그대로 2배였음)."""
    img = Image.open(io.BytesIO(png)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=87)
    b64 = base64.standard_b64encode(buf.getvalue()).decode()
    uri = f"data:image/jpeg;base64,{b64}"
    _el(root, "image", {"x": x, "y": y, "width": w, "height": h,
                        "href": uri, "id": id_, "data-source-ref": source_ref})


def _polygon(root, pts, mx, my, *, fill, opacity=45, id_=None, source_ref=None):
    points = " ".join(f"{mx+x:.1f},{my+y:.1f}" for x, y in pts)
    _el(root, "polygon", {"points": points, "fill": fill, "fill-opacity": opacity / 100,
                          "stroke": fill, "stroke-width": 1, "id": id_, "data-source-ref": source_ref})


def _dot_label(root, mx, my, cx, cy, lines, *, dot=WHITE, id_=None, source_ref=None, size=14):
    g = _el(root, "g", {"id": id_, "data-source-ref": source_ref})
    x, y = mx + cx, my + cy
    _el(g, "circle", {"cx": x, "cy": y, "r": 6, "fill": dot, "stroke": INK, "stroke-width": 1.2})
    lines = lines if isinstance(lines, list) else [lines]
    longest = max((len(t) for t in lines), default=4)
    w = max(150, 10.5 * longest + 30)
    hh = 26 * len(lines) + 10
    _el(g, "rect", {"x": x + 10, "y": y - hh / 2, "width": w, "height": hh, "rx": 5,
                    "fill": INK, "fill-opacity": 0.74})
    for i, ln in enumerate(lines):
        _el(g, "text", {"x": x + 10 + w / 2, "y": y - hh / 2 + 22 + i * 26, "font-size": size,
                        "fill": WHITE, "font-weight": "bold", "text-anchor": "middle"}, ln)
    return g


def _site_marker(root, mx, my, cx, cy, parcel_pts=None, *, source_ref="site"):
    """SITE 표기 — 필지 형상(있으면) + 십자, 없으면 빨간 알약. (style.site_marker의 SVG판)"""
    if parcel_pts and len(parcel_pts) >= 3:
        g = _el(root, "g", {"id": "site", "data-source-ref": source_ref})
        pts = " ".join(f"{mx+x:.1f},{my+y:.1f}" for x, y in parcel_pts)
        _el(g, "polygon", {"points": pts, "fill": RED, "fill-opacity": 0.26, "stroke": WHITE, "stroke-width": 2.5})
        ccx = mx + sum(p[0] for p in parcel_pts) / len(parcel_pts)
        ccy = my + sum(p[1] for p in parcel_pts) / len(parcel_pts)
        _el(g, "path", {"d": f"M {ccx-11:.1f} {ccy:.1f} L {ccx+11:.1f} {ccy:.1f} "
                             f"M {ccx:.1f} {ccy-11:.1f} L {ccx:.1f} {ccy+11:.1f}",
                        "stroke": RED, "stroke-width": 4.5})
        _el(g, "text", {"x": ccx, "y": ccy + 30, "font-size": 15, "fill": WHITE, "font-weight": "bold",
                        "text-anchor": "middle"}, "SITE")
    else:
        x, y = mx + cx, my + cy
        g = _el(root, "g", {"id": "site", "data-source-ref": source_ref})
        _el(g, "rect", {"x": x - 48, "y": y - 23, "width": 96, "height": 46, "rx": 11,
                        "fill": RED, "stroke": WHITE, "stroke-width": 2.2})
        _el(g, "text", {"x": x, "y": y + 7, "font-size": 18, "fill": WHITE, "font-weight": "bold",
                        "text-anchor": "middle"}, "SITE")


def _compass(root, x, y):
    _el(root, "text", {"x": x, "y": y, "font-size": 22, "fill": WHITE, "font-weight": "bold",
                       "text-anchor": "middle"}, "N")


def _sector_arc(root, mx, my, cx, cy, r, a1, a2, color, *, id_=None, source_ref=None):
    """방위각(0=N, 시계방향) a1→a2 호. 화면좌표(y 아래로 증가) 기준."""
    def pt(a):
        return cx + r * math.sin(math.radians(a)), cy - r * math.cos(math.radians(a))
    x1, y1 = pt(a1)
    x2, y2 = pt(a2)
    large = 1 if (a2 - a1) % 360 > 180 else 0
    d = f"M {mx+x1:.1f} {my+y1:.1f} A {r:.1f} {r:.1f} 0 {large} 1 {mx+x2:.1f} {my+y2:.1f}"
    _el(root, "path", {"d": d, "fill": "none", "stroke": color, "stroke-width": 11,
                       "id": id_, "data-source-ref": source_ref})


def _caption(root, mx, runs):
    """하단 레드 캡션밴드. runs=[(text, color|None, bold)]."""
    y0 = HEADER_H + MAP
    _el(root, "rect", {"x": 0, "y": y0, "width": TOTAL_W, "height": CAPTION_H, "fill": RED})
    t = _el(root, "text", {"x": mx, "y": y0 + CAPTION_H / 2 + 10, "font-size": 23})
    for text, color, bold in runs:
        _el(t, "tspan", {"fill": color or WHITE, "font-weight": "bold" if bold else "normal"}, text)


def _panel_head(root, px, y, title):
    _el(root, "rect", {"x": px, "y": y, "width": 6, "height": 40, "fill": RED})
    _el(root, "text", {"x": px + 22, "y": y + 30, "font-size": 22, "fill": WHITE, "font-weight": "bold"}, title)


# ── 지도 1: 광역입지도 ──
def svg_wide(address, lat, lon, law, site) -> Optional[str]:
    fac = clients.fetch_facilities(address, ["지하철역"], 2000)
    res = clients.fetch_basemap(lat, lon, 2000, 1500)
    if not res:
        return None
    meta, png = res
    size = 1500
    z, mcx, mcy, rpx = int(meta["zoom"]), float(meta["cx"]), float(meta["cy"]), float(meta["radius_px"])
    lp = (site or {}).get("land_price") or {}
    bd = (site or {}).get("building") or {}
    law = law or {}

    def sbase(n):
        return re.sub(r"\(.*?\)", "", re.sub(r"\s*\d+번출구.*$", "", re.sub(r"\s*\d+호선.*$", "", n))).strip()

    stations = {}
    for f in (fac or {}).get("results", []):
        base = sbase(str(f.get("name") or ""))
        if not base.endswith("역") or f.get("lat") is None:
            continue
        st = stations.setdefault(base, {"name": base, "lat": f["lat"], "lon": f["lon"], "lines": set()})
        st["lines"] |= set(re.findall(r"(\d+)호선", str(f.get("name") or "")))
    stations = sorted(stations.values(), key=lambda s: (s["lat"] - lat) ** 2 + (s["lon"] - lon) ** 2)[:16]

    root, mx, my = _page("광역입지현황", f"PROJECT POSITIONING · {address}")
    _image(root, png, mx, my, size, size, id_="basemap", source_ref="vworld:satellite-tile")
    scx = scy = size / 2
    for rm in (500, 1000, 2000):
        rp = rpx * rm / 2000
        _el(root, "circle", {"cx": mx + scx, "cy": my + scy, "r": rp, "fill": "none", "stroke": WHITE,
                             "stroke-width": 2.5, "stroke-dasharray": "12,9",
                             "id": f"radius-{rm}", "data-source-ref": "computed:basemap-scale"})
        lbl = f"{rm//1000}km" if rm >= 1000 else f"{rm}m"
        _el(root, "text", {"x": mx + scx, "y": my + scy - rp - 12, "font-size": 18, "fill": WHITE,
                           "text-anchor": "middle", "font-weight": "bold"}, lbl)
    for i, s in enumerate(stations):
        cxp, cyp = k.to_canvas(s["lat"], s["lon"], z, mcx, mcy, size)
        if not (10 <= cxp <= size - 10 and 10 <= cyp <= size - 10):
            continue
        first_line = sorted(s["lines"])[0] if s["lines"] else None
        col = _hex(k.LINE_COLOR[first_line]) if first_line in k.LINE_COLOR else GRAY
        _dot_label(root, mx, my, cxp, cyp, s["name"], dot=col,
                  id_=f"station-{i}", source_ref=f"kakao:facilities.results[name={s['name']}]")
    _site_marker(root, mx, my, scx, scy, None, source_ref="site-seed:pnu")
    _compass(root, mx + size - 40, my + 40)

    px = mx + size + GAP
    _panel_head(root, px, my, "대지 개요")
    y = my + 70
    rows = [
        ("위치", address, "site-seed:address"),
        ("지목", ms.parse_jimok(lp.get("jibun")) or "확인필요", "vworld:land_price"),
        ("용도지역", law.get("zone_use") or "확인필요", "law:zone_use"),
        ("개별공시지가",
         f"{lp.get('price_per_sqm'):,}원/㎡ ({lp.get('year')})" if lp.get("price_per_sqm") else "확인필요",
         "vworld:land_price"),
        ("현황", bd.get("name") or "나대지", "molit:building"),
        ("PNU", law.get("pnu") or (site or {}).get("pnu") or "-", "vworld:pnu"),
    ]
    for label, val, ref in rows:
        _el(root, "text", {"x": px, "y": y, "font-size": 13, "fill": RED, "font-weight": "bold"}, label)
        _el(root, "text", {"x": px, "y": y + 24, "font-size": 17, "fill": WHITE, "font-weight": "bold",
                           "data-source-ref": ref, "id": f"info-{label}"}, str(val))
        y += 58
    y += 10
    present = sorted({l for s in stations for l in s["lines"]}, key=int)
    _el(root, "text", {"x": px, "y": y, "font-size": 15, "fill": MUTE, "font-weight": "bold"}, "지하철 노선")
    y += 30
    for l in present:
        col = _hex(k.LINE_COLOR[l]) if l in k.LINE_COLOR else GRAY
        _el(root, "circle", {"cx": px + 10, "cy": y, "r": 9, "fill": col})
        _el(root, "text", {"x": px + 26, "y": y + 6, "font-size": 15, "fill": WHITE, "font-weight": "bold"},
            f"{l}호선")
        y += 32

    names = ", ".join(s["name"] for s in stations[:3]) or "인근 역"
    _caption(root, mx, [
        (f"{law.get('zone_use') or '도심'} · 역세권 입지 — 반경 1km 내 ", WHITE, True),
        (names, HL_HEX, True),
        (" 등 지하철 접근 양호. 광역 교통축과 연계된 통합 거점.", WHITE, True),
    ])
    return _serialize(root)


# ── 지도 2: 건물 용도현황 ──
def svg_use(address, lat, lon, model, parcel=None) -> Optional[str]:
    kinds = list(ms.KIND_USE.keys())
    fac = clients.fetch_facilities(address, kinds, 320)
    res = clients.fetch_basemap(lat, lon, 320, 1500)
    if not res:
        return None
    meta, png = res
    size = 1500
    z, mcx, mcy = int(meta["zoom"]), float(meta["cx"]), float(meta["cy"])
    strong, weak = [], []
    for f in (fac or {}).get("results", []):
        u = ms.KIND_USE.get(f.get("kind"))
        nm = str(f.get("name") or "")
        if u and f.get("lat") is not None:
            is_strong = f.get("kind") in ms._USE_STRONG
            if f.get("kind") == "병원" and any(w in nm for w in ("의원", "치과", "한의원", "동물")):
                is_strong = False
            (strong if is_strong else weak).append((f["lat"], f["lon"], u, nm))
    blds = ms._buildings(model, lat, lon, z, mcx, mcy, size)
    for b in blds:
        def nearest(lst):
            bd, bu, bn = 1e9, None, None
            for (pla, plo, pu, pn) in lst:
                d = clients._haversine_m(b["clat"], b["clon"], pla, plo)
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
        b["use"] = nu or use
        b["name"] = nm if (nm and ms._name_use(nm)) else None

    root, mx, my = _page("건물 용도현황", f"SITE CONTEXT · 주변 건물 용도 · {address}")
    _image(root, png, mx, my, size, size, id_="basemap", source_ref="vworld:satellite-tile")
    for i, b in enumerate(blds):
        ref = "arch-site-model:geometry.buildings"
        if b["name"]:
            ref += f"+kakao:facilities.results[name={b['name']}]"
        _polygon(root, b["pts"], mx, my, fill=_hex(ms.USE[b["use"]][0]),
                 opacity=48 if b["use"] != "미상" else 24, id_=f"bldg-{i}", source_ref=ref)
    named = ms._spread(sorted([b for b in blds if b["name"]], key=lambda b: b["use"] != "주거"), 13, 230)
    for i, b in enumerate(named):
        _dot_label(root, mx, my, b["cx"], b["cy"], [b["name"][:12], ms.USE[b["use"]][1]],
                  id_=f"label-{i}", source_ref=f"kakao:facilities.results[name={b['name']}]")
    parcel_pts = k.parcel_canvas(parcel, z, mcx, mcy, size) if parcel else None
    _site_marker(root, mx, my, size / 2, size / 2, parcel_pts,
                source_ref="law:parcel_geometry" if parcel_pts else "site-seed:pnu")
    _compass(root, mx + size - 40, my + 40)

    cnt = {}
    for b in blds:
        cnt[b["use"]] = cnt.get(b["use"], 0) + 1
    px = mx + size + GAP
    _panel_head(root, px, my, "건물 용도")
    ly = my + 70
    for u in ["주거", "상업", "업무", "공업", "공공", "미상"]:
        col, lab = ms.USE[u]
        _el(root, "rect", {"x": px, "y": ly, "width": 28, "height": 28, "fill": _hex(col), "fill-opacity": 0.72})
        _el(root, "text", {"x": px + 40, "y": ly + 21, "font-size": 17, "fill": WHITE, "font-weight": "bold"},
            f"{lab}  ({cnt.get(u, 0)})")
        ly += 42
    ly += 20
    for line in [f"· 반경 내 건물 {len(blds)}동", "· 용도=주변 시설(kakao) 추정", "  명칭 확인 건물은 실제 용도"]:
        _el(root, "text", {"x": px, "y": ly, "font-size": 14, "fill": MUTE}, line)
        ly += 26

    top = max((u for u in ms.USE if u != "미상"), key=lambda u: cnt.get(u, 0), default="주거")
    _caption(root, mx, [
        ("주변 건물 ", WHITE, True),
        (f"{ms.USE[top][1]} 우세", HL_HEX, True),
        (f" ({cnt.get(top, 0)}/{len(blds)}동) — 다양한 용도가 혼재한 시가지. 용도는 주변시설 기반 추정.",
         WHITE, True),
    ])
    return _serialize(root)


# ── 지도 3: 입지현황(높이) ──
def svg_site(address, lat, lon, model, parcel=None) -> Optional[str]:
    fac = clients.fetch_facilities(address, ms._BLDG_KINDS, 320)
    res = clients.fetch_basemap(lat, lon, 320, 1500)
    if not res:
        return None
    meta, png = res
    size = 1500
    z, mcx, mcy = int(meta["zoom"]), float(meta["cx"]), float(meta["cy"])
    blds = ms._buildings(model, lat, lon, z, mcx, mcy, size)
    ms._match_names(blds, fac or {})
    named = ms._spread(sorted([b for b in blds if b["name"]], key=lambda b: -b["h"]), 14, 220)

    root, mx, my = _page("입지현황", f"SITE CONTEXT · 주변 건물 매싱·높이 · {address}")
    _image(root, png, mx, my, size, size, id_="basemap", source_ref="vworld:satellite-tile")
    for i, b in enumerate(blds):
        ref = "arch-site-model:geometry.buildings"
        if b["name"]:
            ref += f"+kakao:facilities.results[name={b['name']}]"
        _polygon(root, b["pts"], mx, my, fill=_hex(k.hcol(b["h"])), opacity=55, id_=f"bldg-{i}", source_ref=ref)
    for i, b in enumerate(named):
        fl = max(1, round(b["h"] / 3.0))
        _dot_label(root, mx, my, b["cx"], b["cy"], [b["name"][:12], f"{fl}층 · 약 {int(b['h'])}m"],
                  id_=f"label-{i}", source_ref=f"kakao:facilities.results[name={b['name']}]+arch-site-model:height")
    parcel_pts = k.parcel_canvas(parcel, z, mcx, mcy, size) if parcel else None
    _site_marker(root, mx, my, size / 2, size / 2, parcel_pts,
                source_ref="law:parcel_geometry" if parcel_pts else "site-seed:pnu")
    _compass(root, mx + size - 40, my + 40)

    hs = [b["h"] for b in blds]
    px = mx + size + GAP
    _panel_head(root, px, my, "주변 건물 높이")
    ly = my + 70
    for lab, hh in [("저층 ~15m", 10), ("중저 15~35m", 25), ("중고 35~60m", 50), ("고층 60m~", 80)]:
        _el(root, "rect", {"x": px, "y": ly, "width": 28, "height": 28, "fill": _hex(k.hcol(hh)),
                           "fill-opacity": 0.7})
        _el(root, "text", {"x": px + 40, "y": ly + 21, "font-size": 17, "fill": WHITE, "font-weight": "bold"}, lab)
        ly += 42
    ly += 16
    for line in [f"· 반경 내 건물 {len(blds)}동",
                 f"· 최고 {int(max(hs)) if hs else 0}m / 평균 {int(sum(hs)/len(hs)) if hs else 0}m",
                 f"· 라벨 건물 {len(named)}동"]:
        _el(root, "text", {"x": px, "y": ly, "font-size": 14, "fill": MUTE}, line)
        ly += 26

    tall = sum(1 for h in hs if h >= 60)
    _caption(root, mx, [
        ("주변 ", WHITE, True), (f"{len(blds)}동 중 60m 이상 고층 {tall}동", HL_HEX, True),
        (" — 층수·높이 실측(VWorld), 도로폭은 별도 확인.", WHITE, True),
    ])
    return _serialize(root)


# ── 지도 4: 방향별 조망 ──
def svg_viewring(address, lat, lon, model, parcel=None) -> Optional[str]:
    fac = clients.fetch_facilities(address, ms._BLDG_KINDS, 600)
    res = clients.fetch_basemap(lat, lon, 600, 1500)
    if not res:
        return None
    meta, png = res
    size = 1500
    z, mcx, mcy = int(meta["zoom"]), float(meta["cx"]), float(meta["cy"])
    ox, oy = (model.get("stats") or {})["origin_offset"]
    sx, sy = k.latlon_to_local(lat, lon, ox, oy)
    sect = [0.0] * 8
    blds = []
    for b in (model.get("geometry") or {}).get("buildings") or []:
        fp = b.get("footprint") or []
        if len(fp) < 3:
            continue
        cxl = sum(p[0] for p in fp) / len(fp)
        cyl = sum(p[1] for p in fp) / len(fp)
        dx, dy = cxl - sx, cyl - sy
        if abs(dx) + abs(dy) < 3:
            continue
        brg = (math.degrees(math.atan2(dx, dy)) + 360) % 360
        h = b.get("height") or 0.0
        sect[int(brg // 45)] = max(sect[int(brg // 45)], h)
        clat, clon = k.local_to_latlon(cxl, cyl, ox, oy)
        blds.append({"clat": clat, "clon": clon, "h": h, "name": None})
    ms._match_names(blds, fac or {})
    named = sorted([b for b in blds if b["name"]], key=lambda b: -b["h"])
    views = [k.view_of(h) for h in sect]
    groups, used = [], [False] * 8
    for i in range(8):
        if used[i]:
            continue
        j = i
        while views[(j + 1) % 8] == views[i] and not used[(j + 1) % 8] and (j + 1) % 8 != i:
            j += 1
        for m in range(i, j + 1):
            used[m % 8] = True
        groups.append((i, j, views[i]))

    root, mx, my = _page("방향별 조망 · 건물높이 분석", f"SITE CONTEXT · {address}")
    _image(root, png, mx, my, size, size, id_="basemap", source_ref="vworld:satellite-tile")
    scx = scy = size / 2
    R = size * 0.44
    for gi, (i, j, vk) in enumerate(groups):
        col = _hex(k.VIEW[vk][0])
        a1, a2 = i * 45 + 1.5, (j + 1) * 45 - 1.5
        _sector_arc(root, mx, my, scx, scy, R, a1, a2, col,
                   id_=f"sector-{gi}", source_ref="arch-site-model:geometry.buildings(max-height-per-45deg)")
        mb = ((a1 + a2) / 2) % 360
        rr = R * 1.08
        lx_, ly_ = scx + rr * math.sin(math.radians(mb)), scy - rr * math.cos(math.radians(mb))
        rot = mb if mb <= 180 else mb - 180
        _el(root, "text", {"x": mx + lx_, "y": my + ly_, "font-size": 15, "fill": col, "font-weight": "bold",
                           "text-anchor": "middle",
                           "transform": f"rotate({rot:.1f} {mx+lx_:.1f} {my+ly_:.1f})"}, k.VIEW[vk][1])
    for i, j, vk in groups:
        mb = ((i * 45 + (j + 1) * 45) / 2) % 360
        x2 = scx + R * 0.98 * math.sin(math.radians(mb))
        y2 = scy - R * 0.98 * math.cos(math.radians(mb))
        _el(root, "line", {"x1": mx + scx, "y1": my + scy, "x2": mx + x2, "y2": my + y2,
                           "stroke": WHITE, "stroke-width": 1.2, "stroke-dasharray": "8,8"})
    placed = []
    for bi, b in enumerate(named):
        cxp, cyp = k.to_canvas(b["clat"], b["clon"], z, mcx, mcy, size)
        if not (40 <= cxp <= size - 40 and 40 <= cyp <= size - 40):
            continue
        if all((cxp - p[0]) ** 2 + (cyp - p[1]) ** 2 > 200 ** 2 for p in placed):
            placed.append((cxp, cyp))
            _dot_label(root, mx, my, cxp, cyp, [b["name"][:11], f"{int(b['h'])}m"],
                      id_=f"label-{bi}", source_ref=f"kakao:facilities.results[name={b['name']}]")
        if len(placed) >= 12:
            break
    parcel_pts = k.parcel_canvas(parcel, z, mcx, mcy, size) if parcel else None
    _site_marker(root, mx, my, scx, scy, parcel_pts,
                source_ref="law:parcel_geometry" if parcel_pts else "site-seed:pnu")
    _compass(root, mx + size - 40, my + 40)

    px = mx + size + GAP
    _panel_head(root, px, my, "방향별 조망 요약")
    py = my + 70
    for kk in range(8):
        col, en, kr = k.VIEW[k.view_of(sect[kk])]
        _el(root, "circle", {"cx": px + 14, "cy": py + 14, "r": 10, "fill": _hex(col)})
        _el(root, "text", {"x": px + 40, "y": py + 20, "font-size": 17, "fill": WHITE, "font-weight": "bold"},
            ms.DIRN[kk])
        _el(root, "text", {"x": px + 110, "y": py + 18, "font-size": 13, "fill": _hex(col), "font-weight": "bold"},
            en)
        _el(root, "text", {"x": px + 110, "y": py + 40, "font-size": 12, "fill": MUTE},
            f"{kr} · 최고 {int(sect[kk])}m")
        py += 58
    opens = [ms.DIRN[kk] for kk in range(8) if k.view_of(sect[kk]) in ("OPEN", "LOW")]
    runs = ([('·'.join(opens), HL_HEX, True),
             (" 방향이 상대적으로 열려 조망·채광 유리 — 그 외는 고층 차폐 검토 필요.", WHITE, True)]
            if opens else
            [("사방이 중·고층으로 둘러싸여 개방면 제한적", HL_HEX, True),
             (" — 저층부 조망·상층부 향 확보 전략 검토.", WHITE, True)])
    _caption(root, mx, runs)
    return _serialize(root)


def build_map_svgs(address: str, use_type: str = "주거", radius: int = 1000) -> dict:
    """주소 → 지도 4종(광역·용도·높이·조망) SVG dict. 실패한 개별 지도는 건너뛴다(부분 결과 허용).

    데이터 fetch·건물매싱·용도분류·조망섹터 계산은 `map_slides.build_full_deck`과 동일 —
    새 계산 로직 0, 렌더 타깃만 SVG.
    """
    from app.services.site_seed import build_site
    try:
        s = build_site(address)
        lat, lon, pnu = s.lat, s.lon, (s.pnu or "")
    except Exception:  # noqa: BLE001 — 주소 해석 실패는 하드블록
        raise ValueError("주소 해석 실패")
    if lat is None:
        raise ValueError("주소 해석 실패")

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_model = ex.submit(clients.fetch_model, address, 350)
        f_law = ex.submit(clients.fetch_law, address, pnu)
        f_site = ex.submit(clients.fetch_site, address)
        model, law, site = f_model.result(), f_law.result(), f_site.result()
    parcel = (law or {}).get("parcel_geometry")

    out: dict = {}
    for key, fn in [("wide", lambda: svg_wide(address, lat, lon, law, site))]:
        try:
            svg = fn()
            if svg:
                out[key] = svg
        except Exception:  # noqa: BLE001 — 지도 하나 실패해도 나머지는 살린다
            pass
    if model:
        for key, fn in [
            ("use", lambda: svg_use(address, lat, lon, model, parcel)),
            ("site", lambda: svg_site(address, lat, lon, model, parcel)),
            ("viewring", lambda: svg_viewring(address, lat, lon, model, parcel)),
        ]:
            try:
                svg = fn()
                if svg:
                    out[key] = svg
            except Exception:  # noqa: BLE001
                pass
    return out
