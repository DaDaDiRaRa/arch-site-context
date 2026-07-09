"""arch-site-model 결합 — 넘겨받은 물리 모델 출력을 압축 요약 (INTEGRATION.md §4).

터읽기는 arch-site-model 을 **호출하지 않는다**(provider 경계). assembler 가 넘긴 arch-site-model
`POST /api/generate` 응답(dict)을 받아 보드 렌더·패널에 필요한 것만 뽑는다. **새 숫자 0** — 값은
arch-site-model 이 만든 그대로, 우리는 골라 담을 뿐 (절대 원칙 1·2). 방어적: 필드 없으면 None/빈값.
"""

from __future__ import annotations

from typing import Any, List, Optional

from app.schemas.site_model import MAX_FOOTPRINTS, SiteModelSummary


def _num(v: Any) -> Optional[float]:
    """숫자로 해석 가능하면 float, 아니면 None (추정 안 함)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _footprint(b: Any) -> Optional[List[List[float]]]:
    """건물 1개의 외곽선 → [[x,y],...] (로컬 미터). 형식 이상하면 None."""
    if not isinstance(b, dict):
        return None
    ring = b.get("footprint")
    if not isinstance(ring, list) or len(ring) < 3:
        return None
    pts: List[List[float]] = []
    for p in ring:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            return None
        x, y = _num(p[0]), _num(p[1])
        if x is None or y is None:
            return None
        pts.append([x, y])
    return pts


def summarize_model(raw: Any) -> Optional[SiteModelSummary]:
    """arch-site-model 응답(dict) → SiteModelSummary. 유효 데이터 없으면 None (억지 생성 안 함)."""
    if not isinstance(raw, dict):
        return None

    geometry = raw.get("geometry") if isinstance(raw.get("geometry"), dict) else {}
    stats = raw.get("stats") if isinstance(raw.get("stats"), dict) else {}
    files = raw.get("files") if isinstance(raw.get("files"), dict) else {}
    provenance = raw.get("provenance") if isinstance(raw.get("provenance"), dict) else {}
    warnings = raw.get("warnings") if isinstance(raw.get("warnings"), list) else []

    buildings = geometry.get("buildings") if isinstance(geometry.get("buildings"), list) else []
    footprints: List[List[List[float]]] = []
    heights: List[float] = []
    truncated = 0
    for b in buildings:
        fp = _footprint(b)
        if fp is None:
            continue
        if len(footprints) >= MAX_FOOTPRINTS:
            truncated += 1
            continue
        footprints.append(fp)
        h = _num(b.get("height")) if isinstance(b, dict) else None
        heights.append(h if h is not None else 0.0)

    # 유효성: 건물 요약이든 통계든 하나는 있어야 의미 (전부 비면 None — no silent empty)
    has_signal = bool(footprints) or bool(stats) or bool(files)
    if not has_signal:
        return None

    elev = stats.get("elev_range_m")
    elev_range = [float(elev[0]), float(elev[1])] if (
        isinstance(elev, (list, tuple)) and len(elev) >= 2
        and _num(elev[0]) is not None and _num(elev[1]) is not None
    ) else None

    off = stats.get("origin_offset")
    origin = [float(off[0]), float(off[1])] if (
        isinstance(off, (list, tuple)) and len(off) >= 2
        and _num(off[0]) is not None and _num(off[1]) is not None
    ) else None

    bc = _num(stats.get("buildings"))
    sol = _num(stats.get("solids"))
    parcels = _num(stats.get("cadastral_parcels"))
    rad = _num(provenance.get("radius_m")) if provenance.get("radius_m") is not None else _num(stats.get("radius_m"))

    note = ""
    if truncated:
        note = f"미리보기는 건물 {MAX_FOOTPRINTS}개까지 표시 ({truncated}개 생략). 통계·파일은 전체 기준."

    return SiteModelSummary(
        building_count=int(bc) if bc is not None else None,
        solids=int(sol) if sol is not None else None,
        cadastral_parcels=int(parcels) if parcels is not None else None,
        elev_range_m=elev_range,
        origin_offset=origin,
        radius_m=int(rad) if rad is not None else None,
        footprints=footprints,
        heights_m=heights,
        files={k: v for k, v in files.items() if isinstance(v, str)},
        provenance={k: v for k, v in provenance.items()},
        warnings=[w for w in warnings if isinstance(w, str)],
        note=note,
    )
