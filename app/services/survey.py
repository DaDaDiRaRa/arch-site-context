"""C1 — 조사범위 걸침 합산 엔진 (CLAUDE.md §8.13 심의 현황팩).

심의도서 '조사대상 행정동 인구·세대수 통계' 표를 코드로 재현. scratchpad c1_engine 의 앱 이식.

파이프라인:
  주소 → kakao.resolve_coord → 대지 H코드/시군구
       → SGIS 읍면동 경계(UTM-K) ∩ 반경 원 → shapely 걸침율(면적비)
       → 각 걸침 행정동 중심 → transcoord → kakao.coord_to_hdong → H코드
       → jumin.fetch_dong_stats(시군구) → 인구·세대 매칭
       → 적용 = 총량 × 걸침율, 계 = 대지 시군구 포함분
       → 시군구 경계 넘는 동은 ⚠flagged (생활권 판단은 사람, 절대 원칙 5)

원칙: 걸침율=코드 기하(원칙1·2), 인구·세대=행안부 실측(원칙1), 보간·추정 없음(원칙3),
      한강 등 하드코딩 없음 — 전국 작동. graceful: 실패 조각은 notes 로 정직하게.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import httpx
from shapely.geometry import Point, shape

from app.schemas.survey import SurveyDong, SurveyResult
from app.services import jumin, kakao, sgis


def _norm(n: str) -> str:
    """행정동명 정규화 (제N동 → N동, 공백 제거) — 이름 폴백 매칭용."""
    return re.sub(r"제(\d+동)", r"\1", (n or "").replace(" ", ""))


def survey_area(address: str, radius: int = 1000, ym: Optional[str] = None,
                client: Optional[httpx.Client] = None) -> SurveyResult:
    """조사범위 걸침 합산. 실패 조각은 notes 로 흡수하고 가능한 만큼 채운다 (graceful)."""
    notes: List[str] = []
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        site = kakao.resolve_coord(address)
        site_h = kakao.coord_to_hdong(site["lat"], site["lon"])
        if not site_h:
            return SurveyResult(address=address, radius=radius,
                                notes=["대지 행정동 해석 실패 — 좌표/주소 확인."])
        site_sgg = site_h["code"][:5]

        tok = sgis.get_token(client)
        cx, cy = sgis.to_utmk(site["lat"], site["lon"], tok, client)
        circle = Point(cx, cy).buffer(radius)
        b = radius + 700
        geo = sgis._get(client, "boundary/userarea.geojson",
                        {"accessToken": tok, "cd": "3",
                         "minx": cx - b, "miny": cy - b, "maxx": cx + b, "maxy": cy + b})

        touched: List[dict] = []
        for feat in geo.get("features", []):
            try:
                poly = shape(feat["geometry"])
            except Exception:
                continue
            if poly.area <= 0:
                continue
            ratio = poly.intersection(circle).area / poly.area
            if ratio <= 0.01:
                continue
            touched.append({"name": feat.get("properties", {}).get("adm_nm", ""),
                            "ratio": ratio, "cx": poly.centroid.x, "cy": poly.centroid.y})

        # 각 걸침 폴리곤 중심 → WGS84 → H코드
        for d in touched:
            try:
                tj = sgis._get(client, "transformation/transcoord.json",
                               {"accessToken": tok, "src": "5179", "dst": "4326",
                                "posX": d["cx"], "posY": d["cy"]})
                tr = tj.get("result") or {}
                hd = kakao.coord_to_hdong(float(tr["posY"]), float(tr["posX"]))
                d["hcode"] = hd["code"] if hd else None
                d["sgg"] = d["hcode"][:5] if d["hcode"] else None
            except Exception:
                d["hcode"] = d["sgg"] = None

        # 걸친 시군구별 행안부 인구·세대 (H코드 dict)
        jumin_by_h: Dict[str, dict] = {}
        used_ym = ym or ""
        for sgg in sorted({d["sgg"] for d in touched if d["sgg"]}):
            data, jnotes = jumin.fetch_dong_stats(sgg, ym=ym)
            if data:
                jumin_by_h.update(data.get("dongs", {}))
                used_ym = data.get("ym", used_ym)
            else:
                notes.extend(jnotes)

        # 매칭 + 집계 (대지 시군구 포함분만 계에 합산)
        dongs: List[SurveyDong] = []
        ap_total = ah_total = 0
        for d in sorted(touched, key=lambda x: -x["ratio"]):
            rec = jumin_by_h.get(d["hcode"]) if d.get("hcode") else None
            if not rec:  # H코드 실패 → 이름 정규화 폴백
                short = d["name"].split()[-1] if d["name"] else ""
                rec = next((v for v in jumin_by_h.values()
                            if _norm(v.get("name", "")) == _norm(short)), None)
            same = (d.get("sgg") == site_sgg) if d.get("sgg") else None
            if not rec:
                dongs.append(SurveyDong(name=d["name"].split()[-1] if d["name"] else d["name"],
                                        hcode=d.get("hcode"), ratio=round(d["ratio"], 4),
                                        same_sgg=same, matched=False))
                continue
            pop, hh = rec.get("population"), rec.get("households")
            ap = round(pop * d["ratio"]) if pop is not None else None
            ah = round(hh * d["ratio"]) if hh is not None else None
            # same is True(대지 시군구)만 계에 합산. False(타시군구)·None(시군구 미해석) 은
            # 모두 ⚠플래그·계 제외 — 미해석 동을 조용히 누락하지 않는다(정직성).
            flagged = same is not True
            dongs.append(SurveyDong(
                name=rec.get("name") or d["name"], hcode=d.get("hcode"),
                ratio=round(d["ratio"], 4), total_pop=pop, total_hh=hh,
                applied_pop=ap, applied_hh=ah, same_sgg=same, flagged=flagged, matched=True))
            if same is True and ap is not None and ah is not None:
                ap_total += ap
                ah_total += ah

        if any(dg.flagged and dg.same_sgg is False for dg in dongs):
            notes.append("타 시군구 걸침 행정동은 ⚠표시(생활권 검토 필요) — 계에서 제외했습니다.")
        if any(dg.same_sgg is None and dg.matched for dg in dongs):
            notes.append("시군구 미해석 행정동은 ⚠표시 — 계에서 제외했습니다(확인 필요).")

        return SurveyResult(
            address=address, site_dong=site_h.get("name", ""), site_sgg=site_sgg,
            site_lat=site["lat"], site_lon=site["lon"],
            radius=radius, ym=used_ym, dongs=dongs,
            applied_pop_total=ap_total, applied_hh_total=ah_total, notes=notes)
    finally:
        if own:
            client.close()
