"""C7 — 주변현황도 엔진 (CLAUDE.md §8.13, 심의 슬라이드 4~6).

대지 반경 내 여가·교육·주거·관공서·교통 시설을 카카오로 수집(절대 원칙 1),
데이터 룰로 '주변현황' 서술문 조립(LLM 0·새 숫자 0). 도로폭·재개발 경계는 소스 없어 안 만듦.
설정(카테고리·키워드·색)은 surroundings.json (원칙 7).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import httpx

from app.schemas.surroundings import SurroundCategory, SurroundItem, SurroundingsResult
from app.services import kakao
from app.services.geo import haversine_m

_PATH = Path(__file__).resolve().parent.parent / "data" / "surroundings.json"


def load_config() -> dict:
    if not _PATH.exists():
        return {"categories": [], "max_per_category": 20}
    return json.loads(_PATH.read_text(encoding="utf-8"))


def _default_rings(radius: int) -> List[int]:
    """현황도 반경밴드. 심의 관행 밴드(250/500/750/1000…) 중 반경 이하 + 최외곽=반경.
    최외곽 링이 항상 실제 조사반경과 같아, 반경 내 수집 핀이 모든 링 밖에 놓이지 않는다.
    """
    band = [r for r in (250, 500, 750, 1000, 1500, 2000) if r < radius]
    band.append(radius)
    return sorted(set(band))[-4:]  # 너무 많으면 바깥쪽 4개만


def _clean_name(name: str, suffix) -> str:
    """'단지명 후문' → '단지명' — suffix(시설 접미)에서 잘라 대표 시설명으로."""
    if not suffix:
        return name.strip()
    sufs = suffix if isinstance(suffix, list) else [suffix]
    ends = [name.find(s) + len(s) for s in sufs if s in name]
    ends = [e for e in ends if e > 0]
    return name[:min(ends)].strip() if ends else name.strip()


def _collect_category(cat: dict, lat: float, lon: float, radius: int, cap: int,
                      noise: List[str], client: httpx.Client) -> SurroundCategory:
    seen: set = set()
    rows: List[dict] = []
    for kw in cat.get("keywords", []):
        try:
            docs = kakao.search_keyword(kw, lat, lon, radius, client=client,
                                        category_group_code=cat.get("code"))
        except Exception:
            continue
        for d in docs:
            raw = d["name"]
            if any(tok in raw for tok in noise):  # 행정실·후문·ATM 등 오탐 제거
                continue
            dist = haversine_m(lat, lon, d["lat"], d["lon"])
            if dist > radius:
                continue
            name = _clean_name(raw, cat.get("suffix"))
            key = name.replace(" ", "")  # 정제 이름으로 중복 제거(같은 단지 하위시설 합침)
            if not name or key in seen:
                continue
            seen.add(key)
            rows.append({"name": name, "addr": d.get("addr", ""),
                         "dist_m": round(dist), "lat": d["lat"], "lon": d["lon"]})
    rows.sort(key=lambda r: r["dist_m"])
    capped = rows[:cap]
    color = tuple(cat.get("color", [120, 120, 120]))
    notes = [] if len(rows) <= cap else [f"{len(rows)}건 중 가까운 {cap}건만 표시(참고)."]
    return SurroundCategory(
        name=cat["name"], count=len(rows),
        items=[SurroundItem(**r) for r in capped], color=color, notes=notes)


def _narrative(radius: int, cats: List[SurroundCategory], cfg: dict) -> str:
    """주변현황 서술문 — 카테고리별 개수·대표 이름으로 문장 조립 (룰, LLM 0)."""
    narr_map = {c["name"]: c.get("narr", c["name"]) for c in cfg.get("categories", [])}
    by = {c.name: c for c in cats}
    parts: List[str] = []

    tr = by.get("교통")
    if tr and tr.count:
        names = ", ".join(i.name for i in tr.items[:3])
        parts.append(f"{narr_map.get('교통', '지하철')} {names} 인접")
    edu = by.get("교육")
    if edu and edu.count:
        names = ", ".join(i.name for i in edu.items[:3])
        parts.append(f"{narr_map.get('교육', '교육시설')} {edu.count}개소({names} 등)")
    leis = by.get("여가")
    if leis and leis.count:
        names = ", ".join(i.name for i in leis.items[:2])
        parts.append(f"{narr_map.get('여가', '공원')} {leis.count}개소({names} 등)")
    gov = by.get("관공서")
    if gov and gov.count:
        names = ", ".join(i.name for i in gov.items[:3])
        parts.append(f"{narr_map.get('관공서', '관공서')} {names} 위치")
    res = by.get("주거")
    if res and res.count:
        parts.append(f"주변 {narr_map.get('주거', '주거단지')} {res.count}개소")

    if not parts:
        return f"반경 {radius}m 내 수집된 생활편익시설이 없습니다(확인 필요)."
    return f"대상지 반경 {radius}m 내 " + " · ".join(parts) + " 등 생활편익·자연환경 인접."


def collect_surroundings(address: str, radius: int = 1000,
                         client: Optional[httpx.Client] = None) -> SurroundingsResult:
    """주소 → 주변현황 카테고리 + 서술문. graceful."""
    own = client is None
    client = client or httpx.Client(timeout=20.0)
    try:
        site = kakao.resolve_coord(address, client=client)
        lat, lon = site["lat"], site["lon"]
        cfg = load_config()
        cap = cfg.get("max_per_category", 20)
        noise = cfg.get("_noise_tokens", [])
        cats = [_collect_category(c, lat, lon, radius, cap, noise, client)
                for c in cfg.get("categories", [])]
        return SurroundingsResult(
            address=address, site_lat=lat, site_lon=lon, radius=radius,
            ring_radii=_default_rings(radius), categories=cats,
            narrative=_narrative(radius, cats, cfg))
    finally:
        if own:
            client.close()
