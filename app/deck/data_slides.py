"""데이터 팩트 슬라이드 — 지역통계·수급진단·대지정보·생활맥락·주변현황도·주변시설(종류별 상세).

터읽기 /board·/surroundings·/facilities 실데이터를 지도 슬라이드와 **같은 디자인 언어**
(다크 프레임·대괄호 타이틀·네이티브 표/카드·레드 캡션밴드)로 렌더. 새 숫자 0 — 값은 그대로.
전부 graceful — 데이터 없으면 슬라이드 안 만들고 False 반환(no silent skip은 호출부 notes).
"""
from __future__ import annotations

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Cm, Emu, Pt

from app.deck import clients
from app.deck.clients import _bearing8
import app.deck.style as k

HL = k.RGBColor(0xFF, 0xE0, 0x66)
GREEN = k.RGBColor(0x4C, 0xC0, 0x5B)
AMBER = k.RGBColor(0xE8, 0x8A, 0x1E)

# 주변시설 종류 (프론트 B탭 KIND_OPTIONS 와 동일) + 핀·범례 색
FACILITY_KINDS = ["어린이집", "경로당", "학교", "병원", "약국", "공원",
                  "도서관", "지하철역", "버스정류장", "카페"]
KIND_COLOR = {
    "어린이집": (0xF5, 0xA6, 0x23), "경로당": (0xBD, 0x50, 0xA8), "학교": (0x35, 0x9F, 0xE0),
    "병원": (0xE8, 0x3A, 0x2F), "약국": (0x4C, 0xC0, 0x5B), "공원": (0x2E, 0xA0, 0x50),
    "도서관": (0xC8, 0x81, 0x3C), "지하철역": (0x00, 0x52, 0xA4), "버스정류장": (0x74, 0x7F, 0x00),
    "카페": (0x96, 0x6E, 0x46),
}


def _num(v):
    """숫자 → 천단위 구분·소수 1자리. 문자열은 그대로, None은 '-'."""
    if v is None:
        return "-"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f):
        return f"{int(f):,}"
    return f"{f:,.1f}"


def _radius_label(rm):
    """반경(m) → 링 라벨. 500→'500m', 1000→'1km', 1500→'1.5km', 2000→'2km'."""
    if rm >= 1000:
        return f"{rm // 1000}km" if rm % 1000 == 0 else f"{rm / 1000:g}km"
    return f"{rm}m"


def _level_col(lv):
    """수급 수준 → 방향색 (높음/많음=주황, 낮음/적음=파랑, 평이/보통=회색). 판정 아님."""
    if lv in ("높음", "많음"):
        return k.IDX_UP
    if lv in ("낮음", "적음"):
        return k.IDX_DOWN
    return k.MUTE


def _badge(sl, x, y, text, col):
    w = Cm(0.9 + 0.5 * len(str(text)))
    k.rect(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, Cm(0.74), fill=col, alpha_pct=92)
    k.tb(sl, x, y, w, Cm(0.74), text, size=10.5, color=k.WHITE, bold=True,
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return w


# ── 1. 지역통계 (발산형 막대차트 + 총량 KPI) ──
def slide_region_stats(prs, address, region, facts, implications) -> bool:
    facts = [f for f in (facts or []) if f.get("item")]
    if not facts:
        return False
    rname = (region or {}).get("name") or ""
    sl = k.blank_slide(prs)
    k.bracket_title(sl, "지역통계", f"REGIONAL STATISTICS · {rname} 기준 · 전국=100 대비 (시군구 평균)")

    n = k.index_chart(sl, facts, top=4.6, count=7)
    abs_facts = [f for f in facts if not isinstance(f.get("index"), (int, float))][:4]
    if abs_facts:
        cw, gap = Cm(9.3), Cm(0.5)
        ky = 4.6 + n * 1.75 + 0.7
        k.panel_head(sl, Cm(1.3), Cm(ky), "총량 지표 (전국=100 무의미한 절대수)", w=Cm(22), size=13)
        for i, f in enumerate(abs_facts):
            unit = f.get("unit") or ""
            k.kpi_card(sl, Cm(1.3) + i * (cw + gap), Cm(ky + 1.1), cw, Cm(3.0),
                       f.get("item", ""), f"{_num(f.get('value'))}{unit}", f.get("scope") or rname)

    k.caption_band(sl, [(f"{rname} 기준 인구·가구 통계 ", k.WHITE, True),
                        (f"{len(facts)}개 지표", HL, True),
                        (" · 시군구 평균값이며 대지 고유값이 아님(참고)", k.WHITE, True)])
    return True


# ── 2. 주변시설 요약 (종류별 개수) ──
def slide_facilities(prs, address, facilities, radius) -> bool:
    counts = (facilities or {}).get("counts") or {}
    band = counts.get(str(radius)) or {}
    if not band:
        for v in counts.values():
            band = v or {}
            if band:
                break
    band = {kk: vv for kk, vv in band.items() if vv}
    if not band:
        return False
    sl = k.blank_slide(prs)
    k.bracket_title(sl, "주변 시설", f"NEARBY FACILITIES · 반경 {radius}m 내 생활시설 개수 (종류별 상세는 다음 슬라이드)")

    items = sorted(band.items(), key=lambda kv: -kv[1])
    total = sum(v for _, v in items)
    half = (len(items) + 1) // 2
    cols = [items[:half], items[half:]]
    xs = [Cm(1.3), Cm(21.5)]
    for ci, col in enumerate(cols):
        if not col:
            continue
        rows = [[kind, str(cnt)] for kind, cnt in col]
        k.table(sl, xs[ci], Cm(3.6), Cm(19.0), ["시설 종류", "개수"], rows,
                ratios=[4.0, 1.4], fs=11, row_h=Cm(0.95))

    top = items[0]
    k.caption_band(sl, [(f"반경 {radius}m 내 주요 생활시설 ", k.WHITE, True),
                        (f"총 {total}개", HL, True),
                        (f" — 최다 {top[0]} {top[1]}개. 카카오·VWorld 실측.", k.WHITE, True)])
    return True


# ── 2b. 시설 종류별 상세 (지도 핀 + 이름·거리 목록, 종류마다 1장) ──
def _facility_detail_slide(prs, address, kind, items, radius, bm, clat, clon):
    sl = k.blank_slide(prs)
    col = k.RGBColor(*KIND_COLOR.get(kind, (120, 120, 120)))
    shown = items[:20]
    k.bracket_title(sl, f"주변시설 · {kind}", f"NEARBY · {kind} · 반경 {radius}m 내 {len(items)}개소")
    size = 1500
    if bm:
        meta, png = bm
        png = k.prep_satellite(png)
        z, mcx, mcy = int(meta["zoom"]), float(meta["cx"]), float(meta["cy"])
        rpx = float(meta["radius_px"])
        ex, ey, scale = k.add_map(sl, png, Cm(1.3), Cm(2.9), Cm(25.5), size)
        scx = scy = size / 2
        for rm in (500, 1000, 2000):
            if rm > radius:
                continue
            rp = rpx * rm / radius
            k.rect(sl, MSO_SHAPE.OVAL, ex(scx - rp), ey(scy - rp),
                   Emu(int(2 * rp * scale)), Emu(int(2 * rp * scale)), line=k.WHITE, lw=Pt(1.0), dash="dash")
            k.tb(sl, ex(scx) - Cm(1.0), ey(scy - rp) - Cm(0.52), Cm(2.0), Cm(0.5), _radius_label(rm),
                 size=9, color=k.WHITE, bold=True, align=PP_ALIGN.CENTER, wrap=False)
        for i, f in enumerate(shown):
            if f.get("lat") is None:
                continue
            cxp, cyp = k.to_canvas(f["lat"], f["lon"], z, mcx, mcy, size)
            if not (6 <= cxp <= size - 6 and 6 <= cyp <= size - 6):
                continue
            r = Cm(0.28)
            k.rect(sl, MSO_SHAPE.OVAL, Emu(int(ex(cxp))) - r, Emu(int(ey(cyp))) - r, r * 2, r * 2,
                   fill=col, line=k.WHITE, lw=Pt(0.75))
            # 번호 — 두 자리(10↑)도 한 줄로 (wrap=False + 넓은 박스 가운데정렬)
            k.tb(sl, Emu(int(ex(cxp))) - Cm(0.5), Emu(int(ey(cyp))) - Cm(0.3), Cm(1.0), Cm(0.6),
                 str(i + 1), size=9, color=k.WHITE, bold=True,
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, wrap=False)
        k.site_pill(sl, ex, ey, scx, scy)
        k.n_compass(sl, Cm(25.0), Cm(3.2))
    else:
        k.tb(sl, Cm(1.3), Cm(12), Cm(25), Cm(2), "위성 basemap 확인 불가 — 목록만", size=13, color=k.MUTE)

    px = 28.5
    k.panel_head(sl, Cm(px), Cm(2.9), f"{kind} 목록", w=Cm(13))
    rows = []
    for i, f in enumerate(shown):
        brg = ""
        if clat is not None and f.get("lat") is not None:
            brg = _bearing8(clat, clon, f["lat"], f["lon"])
        rows.append([str(i + 1), (f.get("name") or "")[:16], f"{f.get('dist_m', '-')}m", brg])
    k.table(sl, Cm(px), Cm(4.3), Cm(13.0), ["No", "이름", "거리", "방위"], rows,
            ratios=[0.7, 3.7, 1.2, 1.0], fs=8.5, row_h=Cm(0.6), header_h=Cm(0.72))
    if len(items) > len(shown):
        k.tb(sl, Cm(px), Cm(4.3) + Cm(0.72) + Cm(0.6) * len(shown) + Cm(0.2), Cm(13), Cm(0.6),
             f"외 {len(items) - len(shown)}개소 (거리순 상위 {len(shown)}개 표기)", size=9, color=k.MUTE)

    near = ", ".join((f.get("name") or "")[:10] for f in shown[:3])
    k.caption_band(sl, [(f"{kind} ", k.WHITE, True), (f"{len(items)}개소", HL, True),
                        (f" · 최근접 {near}. 카카오 실측 (번호=지도 핀).", k.WHITE, True)])


def slide_facility_details(prs, address, facilities, radius) -> int:
    """종류별 상세 슬라이드를 여러 장 추가. 반환=추가한 슬라이드 수."""
    res = (facilities or {}).get("results") or []
    if not res:
        return 0
    center = (facilities or {}).get("center") or {}
    clat, clon = center.get("lat"), center.get("lon")
    by_kind = {}
    for f in res:
        by_kind.setdefault(f.get("kind"), []).append(f)
    bm = clients.fetch_basemap(clat, clon, radius, 1500) if clat is not None else None
    order = [kk for kk in FACILITY_KINDS if kk in by_kind] + [kk for kk in by_kind if kk not in FACILITY_KINDS]
    n = 0
    for kind in order:
        items = sorted(by_kind.get(kind) or [], key=lambda x: x.get("dist_m") or 1e9)
        if not items:
            continue
        _facility_detail_slide(prs, address, kind, items, radius, bm, clat, clon)
        n += 1
    return n


# ── 3. 수급진단 (수요↔공급 카드) ──
def slide_diagnose(prs, address, diagnoses) -> bool:
    di = [d for d in (diagnoses or []) if d.get("name")]
    if not di:
        return False
    sl = k.blank_slide(prs)
    k.bracket_title(sl, "수급진단", "SUPPLY vs DEMAND · 인구 수요 × 시설 공급 (참고)")

    W, RH = Cm(19.3), 4.6
    xs = [Cm(1.3), Cm(21.4)]
    for i, d in enumerate(di[:6]):
        x, y = xs[i % 2], Cm(3.6 + (i // 2) * RH)
        dem = d.get("demand") or {}
        sup = d.get("supply") or {}
        k.rect(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, W, Cm(4.2), fill=k.PANEL)
        k.tb(sl, x + Cm(0.5), y + Cm(0.32), W - Cm(1), Cm(0.8), d.get("name", ""), size=15, color=k.WHITE, bold=True)
        # 수요 행
        dlv = dem.get("level", "-")
        k.tb(sl, x + Cm(0.5), y + Cm(1.35), Cm(2.6), Cm(0.7), "수요", size=11, color=k.MUTE, bold=True)
        k.tb(sl, x + Cm(3.1), y + Cm(1.33), Cm(11), Cm(0.7),
             f"{dem.get('item', '')} {_num(dem.get('value'))}{dem.get('unit', '')}", size=11, color=k.WHITE)
        bw = _badge(sl, x + W - Cm(0.5) - Cm(0.9 + 0.5 * len(dlv)), y + Cm(1.3), dlv, _level_col(dlv))
        # 공급 행
        slv = sup.get("level", "-")
        kinds = ", ".join((sup.get("kinds") or [])[:2])
        k.tb(sl, x + Cm(0.5), y + Cm(2.28), Cm(2.6), Cm(0.7), "공급", size=11, color=k.MUTE, bold=True)
        k.tb(sl, x + Cm(3.1), y + Cm(2.26), Cm(11), Cm(0.7),
             f"{sup.get('count', '-')}개  ({kinds})", size=11, color=k.WHITE)
        _badge(sl, x + W - Cm(0.5) - Cm(0.9 + 0.5 * len(slv)), y + Cm(2.23), slv, _level_col(slv))
        # 신호
        k.tb(sl, x + Cm(0.5), y + Cm(3.25), W - Cm(1), Cm(0.8), f"→ {d.get('signal', '')}", size=11.5, color=HL, bold=True)

    k.caption_band(sl, [("수요(인구) × 공급(반경 시설) 교차 ", k.WHITE, True), (f"{len(di)}건", HL, True),
                        (" · 부족/과잉은 휴리스틱·'참고', 판단은 사람", k.WHITE, True)])
    return True


# ── 4. 대지정보 ──
def slide_site_info(prs, address, land_price, building, real_estate, hazards) -> bool:
    lp = land_price or {}
    bd = building or {}
    re_ = real_estate or {}
    hz = hazards or {}
    tx = (re_.get("transactions") or [])
    if not any([lp.get("price_per_sqm"), bd.get("name"), bd.get("far"), tx]):
        return False
    sl = k.blank_slide(prs)
    k.bracket_title(sl, "대지정보", f"SITE DATA · 공시지가·건축물대장·재해 · {address}")

    cards = []
    if lp.get("price_per_sqm"):
        cards.append(("개별공시지가", f"{lp['price_per_sqm']:,}", f"원/㎡ ({lp.get('year', '-')})"))
    if bd.get("bcr") is not None:
        cards.append(("건폐율", f"{_num(bd.get('bcr'))}%", "건축물대장"))
    if bd.get("far") is not None:
        cards.append(("용적률", f"{_num(bd.get('far'))}%", "건축물대장"))
    if bd.get("floors_above"):
        cards.append(("층수", f"지상{bd['floors_above']}",
                      f"지하{bd.get('floors_below') or 0} · {bd.get('year_built', '-')}준공"))
    if bd.get("total_area_sqm"):
        cards.append(("연면적", _num(bd.get("total_area_sqm")), "㎡ (건축물대장)"))
    cw, ch, gap = Cm(7.7), Cm(3.4), Cm(0.5)
    for i, (lab, val, sub) in enumerate(cards[:5]):
        k.kpi_card(sl, Cm(1.3) + i * (cw + gap), Cm(3.6), cw, ch, lab, val, sub)

    if bd.get("name"):
        k.tb(sl, Cm(1.3), Cm(7.35), Cm(40), Cm(0.8),
             f"현황 건물: {bd.get('name')} · 주용도 {bd.get('purpose') or '-'}", size=12, color=k.MUTE)

    k.panel_head(sl, Cm(1.3), Cm(8.7), "재해위험 (영향범위 포함 여부·참고)", w=Cm(22), size=14)
    hx = 1.3
    for lab, inz in [("홍수", (hz.get("flood") or {}).get("in_zone")),
                     ("산사태", (hz.get("landslide") or {}).get("in_zone"))]:
        col = AMBER if inz else (GREEN if inz is False else k.MUTE)
        txt = "영향범위 포함" if inz else ("영향범위 밖" if inz is False else "확인불가")
        k.rect(sl, MSO_SHAPE.ROUNDED_RECTANGLE, Cm(hx), Cm(10.0), Cm(6.5), Cm(1.5),
               fill=k.PANEL, line=col, lw=Pt(1.75))
        k.tb(sl, Cm(hx + 0.4), Cm(10.15), Cm(5.8), Cm(0.6), lab, size=12, color=k.WHITE, bold=True)
        k.tb(sl, Cm(hx + 0.4), Cm(10.7), Cm(5.8), Cm(0.6), txt, size=11, color=col, bold=True)
        hx += 7.0
    heat = hz.get("heatwave") or {}
    if heat:
        k.tb(sl, Cm(hx), Cm(10.0), Cm(13), Cm(1.5),
             ["폭염특보 이력", f"경보 {heat.get('alert_count', 0)} · 주의보 {heat.get('warning_count', 0)}"],
             size=11, color=k.MUTE)

    if tx:
        k.panel_head(sl, Cm(1.3), Cm(12.4), "실거래 (참고)", w=Cm(22), size=14)
        rows = []
        for t in tx[:6]:
            price = t.get("price_10k")
            rows.append([
                t.get("category", "-"),
                t.get("name") or t.get("dong") or "-",
                f"{price:,}만원" if price else "-",
                f"{_num(t.get('area_sqm'))}㎡" if t.get("area_sqm") else "-",
                t.get("deal_ym", "-"),
            ])
        k.table(sl, Cm(1.3), Cm(13.7), Cm(28.5), ["종류", "단지/동", "금액", "면적", "거래"],
                rows, ratios=[2.4, 3.2, 2.2, 1.8, 1.8], fs=9.5)

    price_run = (f"공시지가 {lp['price_per_sqm']:,}원/㎡" if lp.get("price_per_sqm") else "공시지가 확인필요")
    k.caption_band(sl, [("대지 실측 정보 ", k.WHITE, True), (price_run, HL, True),
                        (" — VWorld·건축HUB·국토부 실거래·SGIS 재해.", k.WHITE, True)])
    return True


# ── 5. 생활맥락 (보드 합본 / seed context) ──
_CTX_CARDS = [
    ("stores", "상권 점포", lambda v: (_num(v.get("total")), f"반경 {v.get('radius', '')}m · {len(v.get('by_large', []))}업종")),
    ("schools", "학교", lambda v: (_num(v.get("count")), "NEIS 관내")),
    ("childcare", "어린이집", lambda v: (_num(v.get("count")), f"정원 {_num(v.get('total_capacity'))}")),
    ("culture", "문화기반시설", lambda v: (_num(v.get("total")), f"{len(v.get('by_type', {}))}유형")),
    ("real_estate_index", "부동산 매매지수", lambda v: (_num(v.get("value")), v.get("region") or "부동산원")),
    ("weather", "현재 기온", lambda v: (f"{_num(v.get('temp_c'))}℃", "기상청 단기예보")),
    ("living_population", "생활인구", lambda v: (_num(v.get("value")), f"{v.get('date', '')} {v.get('hour', '')}시")),
    ("venues", "공연시설", lambda v: (_num(v.get("count")), v.get("scope") or "KOPIS")),
]


def slide_context(prs, address, context) -> bool:
    ctx = context or {}
    cards = []
    for key, label, fn in _CTX_CARDS:
        v = ctx.get(key)
        if not isinstance(v, dict) or not v:
            continue
        try:
            val, sub = fn(v)
        except Exception:
            continue
        if val in (None, "-", "-℃"):
            continue
        cards.append((label, val, sub))
    if not cards:
        return False
    sl = k.blank_slide(prs)
    k.bracket_title(sl, "생활맥락", "LIVING CONTEXT · 상권·학교·문화·부동산·생활인구 (보드 합본)")

    cw, ch, gx, gy = Cm(9.3), Cm(3.8), Cm(0.6), Cm(0.7)
    for i, (lab, val, sub) in enumerate(cards):
        col, row = i % 4, i // 4
        k.kpi_card(sl, Cm(1.3) + col * (cw + gx), Cm(3.9) + row * (ch + gy), cw, ch, lab, val, sub)

    k.caption_band(sl, [("생활 인프라 지표 ", k.WHITE, True), (f"{len(cards)}종", HL, True),
                        (" — 상권·교육·문화·부동산·생활인구 실API 합본(출처 각 소스).", k.WHITE, True)])
    return True


# ── 6. 주변현황도 ──
def slide_surroundings(prs, address, surroundings) -> bool:
    surr = surroundings or {}
    cats = [c for c in (surr.get("categories") or []) if c.get("count")]
    lat, lon = surr.get("site_lat"), surr.get("site_lon")
    if not cats or not lat:
        return False
    radius = surr.get("radius") or 1000
    bm = clients.fetch_basemap(lat, lon, radius, 1500)

    sl = k.blank_slide(prs)
    k.bracket_title(sl, "주변현황도", f"SURROUNDINGS · 반경 {radius}m · {address}")
    size = 1500
    if bm:
        meta, png = bm
        png = k.prep_satellite(png)
        z, mcx, mcy = int(meta["zoom"]), float(meta["cx"]), float(meta["cy"])
        rpx = float(meta["radius_px"])
        ex, ey, scale = k.add_map(sl, png, Cm(1.3), Cm(2.9), Cm(25.5), size)
        scx = scy = size / 2
        for rm in (surr.get("ring_radii") or [radius]):
            rp = rpx * rm / radius
            if rp <= 0 or rp > size:
                continue
            k.rect(sl, MSO_SHAPE.OVAL, ex(scx - rp), ey(scy - rp),
                   Emu(int(2 * rp * scale)), Emu(int(2 * rp * scale)), line=k.WHITE, lw=Pt(1.0), dash="dash")
            k.tb(sl, ex(scx) - Cm(1.0), ey(scy - rp) - Cm(0.52), Cm(2.0), Cm(0.5), _radius_label(rm),
                 size=9, color=k.WHITE, bold=True, align=PP_ALIGN.CENTER, wrap=False)
        for c in cats:
            col = k.RGBColor(*[int(x) for x in (c.get("color") or [120, 120, 120])])
            for it in (c.get("items") or [])[:40]:
                if it.get("lat") is None:
                    continue
                cxp, cyp = k.to_canvas(it["lat"], it["lon"], z, mcx, mcy, size)
                if not (6 <= cxp <= size - 6 and 6 <= cyp <= size - 6):
                    continue
                r = Cm(0.16)
                k.rect(sl, MSO_SHAPE.OVAL, Emu(int(ex(cxp))) - r, Emu(int(ey(cyp))) - r, r * 2, r * 2,
                       fill=col, line=k.WHITE, lw=Pt(0.5))
        k.site_pill(sl, ex, ey, scx, scy)
        k.n_compass(sl, Cm(25.0), Cm(3.2))
    else:
        k.tb(sl, Cm(1.3), Cm(12), Cm(25), Cm(2), "위성 basemap 확인 불가 — 카테고리 표만", size=13, color=k.MUTE)

    px = 28.5
    k.panel_head(sl, Cm(px), Cm(2.9), "주변현황 카테고리", w=Cm(13))
    ly = 4.5
    for c in cats:
        col = k.RGBColor(*[int(x) for x in (c.get("color") or [120, 120, 120])])
        k.rect(sl, MSO_SHAPE.OVAL, Cm(px), Cm(ly + 0.06), Cm(0.55), Cm(0.55), fill=col, line=k.WHITE, lw=Pt(0.75))
        k.tb(sl, Cm(px + 0.85), Cm(ly), Cm(9), Cm(0.7),
             f"{c.get('name')}  ({c.get('count')})", size=12.5, color=k.WHITE, bold=True)
        ly += 1.05

    narr = (surr.get("narrative") or "").strip()
    if narr:
        k.caption_band(sl, narr[:120])
    else:
        total = sum(c.get("count", 0) for c in cats)
        k.caption_band(sl, [(f"반경 {radius}m 주변현황 ", k.WHITE, True),
                            (f"{len(cats)}개 카테고리·총 {total}건", HL, True),
                            (" — 카카오 실측·서술 룰조립(LLM 0).", k.WHITE, True)])
    return True
