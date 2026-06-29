"""위성 배경 + 핀 + 반경원 + 범례 + 축척 + 출처 합성 → PNG (모드 B, P3).

P1 결과(FacilityResult)를 받아 그 위에 그린다. 좌표 WGS84 → 타일 픽셀 변환은 tiles.py.
모든 수치는 코드가 만든 것(거리·개수)을 그대로 시각화 — 해석 없음.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import List, Optional

import httpx
from PIL import Image, ImageDraw, ImageFont

from app.schemas.facility import FacilityResult
from app.services import tiles

# 캔버스 크기
_W = 820
_H = 820
# 가장 큰 반경원이 캔버스에 들어올 여백(범례·라벨 공간)
_MARGIN_PX = 90

# kind별 핀 색 팔레트 (구분 위주, 순서대로 배정)
_PALETTE = [
    (255, 87, 34),   # 주황
    (33, 150, 243),  # 파랑
    (76, 175, 80),   # 초록
    (255, 193, 7),   # 노랑
    (156, 39, 176),  # 보라
    (0, 188, 212),   # 청록
    (233, 30, 99),   # 분홍
]
_CENTER_COLOR = (255, 255, 255)

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgun.ttf",       # 맑은 고딕 (한글)
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"C:\Windows\Fonts\NanumGothic.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _nice_round(value: float) -> float:
    """축척용 '보기 좋은' 수 (1·2·5 × 10^k) 중 value 이하 최대."""
    if value <= 0:
        return 1.0
    exp = math.floor(math.log10(value))
    base = 10 ** exp
    for m in (5, 2, 1):
        if m * base <= value:
            return m * base
    return base


def compose_map(
    result: FacilityResult,
    radii: List[int],
    basemap: str = "vworld",
    client: Optional[httpx.Client] = None,
    cache_dir: Optional[Path] = None,
    isochrone: Optional[dict] = None,
) -> bytes:
    """FacilityResult → 합성 PNG 바이트."""
    lat = result.center.lat
    lon = result.center.lon
    radii_sorted = sorted(set(int(r) for r in radii))
    max_radius = radii_sorted[-1] if radii_sorted else 2000

    target_px = min(_W, _H) / 2 - _MARGIN_PX
    z = tiles.zoom_for_radius(lat, max_radius, target_px)

    base_img, (cx, cy) = tiles.compose_basemap(
        lat, lon, z, _W, _H, basemap, client=client, cache_dir=cache_dir
    )
    base = base_img.convert("RGBA")
    origin_x = cx - _W / 2
    origin_y = cy - _H / 2

    def to_px(plat: float, plon: float) -> tuple[float, float]:
        gx, gy = tiles.latlon_to_global_px(plat, plon, z)
        return gx - origin_x, gy - origin_y

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    ccx, ccy = _W / 2, _H / 2

    f_small = _font(15)

    # ── 등시선 or 반경원 ────────────────────────────────────
    _ISO_COLORS: dict[int, tuple] = {
        15: (255, 87,  34, 65),   # 주황 — 가장 바깥
        10: (255, 193,  7, 80),   # 노랑
        5:  (76,  175, 80, 100),  # 초록 — 가장 안쪽
    }

    if isochrone and any(len(pts) >= 3 for pts in isochrone.values()):
        # 바깥부터 그려서 안쪽이 위에 쌓임
        for t_min in sorted(isochrone.keys(), reverse=True):
            pts = isochrone[t_min]
            if len(pts) < 3:
                continue
            px_pts = [to_px(p_lat, p_lon) for p_lat, p_lon in pts]
            col = _ISO_COLORS.get(t_min, (200, 200, 200, 60))
            draw.polygon(px_pts, fill=col, outline=(col[0], col[1], col[2], 220))
            # 라벨: 가장 위쪽(y 최소) 꼭짓점 근처
            top_pt = min(px_pts, key=lambda p: p[1])
            draw.text(
                (top_pt[0] + 4, top_pt[1] - 18),
                f"도보 {t_min}분",
                font=f_small,
                fill=(col[0], col[1], col[2], 255),
                stroke_width=2,
                stroke_fill=(0, 0, 0, 200),
            )
    else:
        # TMAP 없거나 실패 — 기존 직선반경 원으로 fallback
        for r in radii_sorted:
            rpx = tiles.meters_to_pixels(r, lat, z)
            draw.ellipse(
                [ccx - rpx, ccy - rpx, ccx + rpx, ccy + rpx],
                outline=(255, 255, 255, 230),
                width=2,
            )
            draw.text(
                (ccx + 4, ccy - rpx - 18),
                f"{r}m",
                font=f_small,
                fill=(255, 255, 255, 255),
                stroke_width=2,
                stroke_fill=(0, 0, 0, 200),
            )

    # ── kind별 색 배정 (counts 키 순서 안정화) ───────────────
    kinds = list(result.counts.get(str(max_radius), {}).keys())
    color_of = {k: _PALETTE[i % len(_PALETTE)] for i, k in enumerate(kinds)}

    # ── 시설 핀 ─────────────────────────────────────────────
    for fac in result.results:
        px, py = to_px(fac.lat, fac.lon)
        if not (-20 <= px <= _W + 20 and -20 <= py <= _H + 20):
            continue
        col = color_of.get(fac.kind, (200, 200, 200))
        rad = 5
        draw.ellipse([px - rad, py - rad, px + rad, py + rad],
                     fill=col + (255,), outline=(255, 255, 255, 255), width=2)

    # ── 중심(대지) 마커 ─────────────────────────────────────
    draw.line([ccx - 10, ccy, ccx + 10, ccy], fill=_CENTER_COLOR + (255,), width=3)
    draw.line([ccx, ccy - 10, ccx, ccy + 10], fill=_CENTER_COLOR + (255,), width=3)
    draw.ellipse([ccx - 6, ccy - 6, ccx + 6, ccy + 6], outline=_CENTER_COLOR + (255,), width=3)

    # ── 범례 (kind별 색·개수 + 등시선 색상) ─────────────────
    f_leg = _font(16)
    f_title = _font(17)
    counts_max = result.counts.get(str(max_radius), {})
    lines = [(k, counts_max.get(k, 0), color_of.get(k, (200, 200, 200))) for k in kinds]
    pad = 12
    sw = 16  # 색 스와치
    row_h = 26

    # 등시선 범례 행 (등시선이 있을 때만)
    iso_keys = sorted(isochrone.keys()) if isochrone and any(len(v) >= 3 for v in isochrone.values()) else []
    iso_extra_rows = len(iso_keys) + (1 if iso_keys else 0)  # 구분선 + 시간 행들

    box_w = 230
    box_h = pad * 2 + 28 + row_h * max(1, len(lines)) + row_h * iso_extra_rows
    lx, ly = 14, 14
    draw.rounded_rectangle([lx, ly, lx + box_w, ly + box_h], radius=10,
                           fill=(0, 0, 0, 150))
    draw.text((lx + pad, ly + pad), f"반경 {max_radius}m 내 시설", font=f_title,
              fill=(255, 255, 255, 255))
    yy = ly + pad + 30
    for name, cnt, col in lines:
        draw.rectangle([lx + pad, yy + 3, lx + pad + sw, yy + 3 + sw], fill=col + (255,),
                       outline=(255, 255, 255, 200))
        draw.text((lx + pad + sw + 8, yy), f"{name}  {cnt}개", font=f_leg,
                  fill=(255, 255, 255, 255))
        yy += row_h

    if iso_keys:
        draw.line([lx + pad, yy + 6, lx + box_w - pad, yy + 6],
                  fill=(255, 255, 255, 100), width=1)
        yy += 16
        for t_min in iso_keys:
            col = _ISO_COLORS.get(t_min, (200, 200, 200))
            draw.rectangle([lx + pad, yy + 3, lx + pad + sw, yy + 3 + sw],
                           fill=col[:3] + (200,), outline=(255, 255, 255, 200))
            draw.text((lx + pad + sw + 8, yy), f"도보 {t_min}분 권역", font=f_leg,
                      fill=(255, 255, 255, 255))
            yy += row_h

    # ── 축척 막대 ───────────────────────────────────────────
    target_m = (_W * 0.22) * tiles.ground_resolution(lat, z)
    nice_m = _nice_round(target_m)
    bar_px = tiles.meters_to_pixels(nice_m, lat, z)
    bx, by = 18, _H - 54
    draw.line([bx, by, bx + bar_px, by], fill=(255, 255, 255, 255), width=4)
    draw.line([bx, by - 5, bx, by + 5], fill=(255, 255, 255, 255), width=4)
    draw.line([bx + bar_px, by - 5, bx + bar_px, by + 5], fill=(255, 255, 255, 255), width=4)
    scale_label = f"{int(nice_m)} m" if nice_m < 1000 else f"{nice_m/1000:g} km"
    draw.text((bx, by - 24), scale_label, font=f_small, fill=(255, 255, 255, 255),
              stroke_width=2, stroke_fill=(0, 0, 0, 200))

    # ── 출처·기준일 ─────────────────────────────────────────
    attr = BASEMAP_ATTR = tiles.BASEMAPS.get(basemap, {}).get("attribution", "")
    foot = f"{attr} / 시설 출처: {result.source} · 기준일 {result.base_date}"
    f_foot = _font(14)
    tb = draw.textbbox((0, 0), foot, font=f_foot)
    fw, fh = tb[2] - tb[0], tb[3] - tb[1]
    draw.rectangle([0, _H - fh - 12, fw + 16, _H], fill=(0, 0, 0, 160))
    draw.text((8, _H - fh - 8), foot, font=f_foot, fill=(255, 255, 255, 255))

    out = Image.alpha_composite(base, overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()
