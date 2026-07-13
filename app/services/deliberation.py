"""심의 현황팩 오케스트레이터 (CLAUDE.md §8.13 C1→C2 글루).

주소 + 신축세대(설계) → 조사범위 걸침 적용세대(C1) + 구 영유아·세대(KOSIS/jumin)
→ 주민공동시설 총량제 부족/충족 판정(C2). 한 호출로 심의 '커뮤니티 총량제 검토' 완성.

- 새 데이터·숫자 안 만듦 — 기존 서비스(survey·quota·kosis·jumin) 조립만 (절대 원칙 1·2).
- graceful: 영유아/구세대 조회 실패해도 나머지는 채우고 notes 로 정직하게 (어린이집만 '확인필요').
- 다획지: new_households 를 list 로 주면 획지별 판정. 걸침 적용세대·구통계는 공유.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Union

import httpx

from app.schemas.quota import QuotaAssessment, QuotaResult
from app.services import jumin, kakao, kosis, quota, stats, survey
from app.services.survey_facilities import collect_survey_facilities


def _gu_infant(sgg_code: str) -> Optional[int]:
    """구 영유아(만 0-4세) 인구 — KOSIS DT_1B04005N. 실패 시 None (추정 안 함)."""
    try:
        res = kosis.fetch_table("101", "DT_1B04005N", sgg_code, itm_id="T2", obj_l2="ALL")
        return int(stats._age_sum(res["rows"], "T2", 0, 4))
    except Exception:
        return None


def _gu_households(sgg_code: str) -> Optional[int]:
    """구 세대 = 행안부 rdoa 행정동 세대 합. 실패 시 None."""
    data, _ = jumin.fetch_dong_stats(sgg_code)
    if not data:
        return None
    total = sum(v.get("households") or 0 for v in data.get("dongs", {}).values())
    return total or None


def assess_quota(address: str,
                 new_households: Union[int, List[int]],
                 *, radius: int = 1000, ym: Optional[str] = None,
                 existing_area: Optional[Dict[str, float]] = None,
                 planned_area: Optional[Dict[str, float]] = None,
                 labels: Optional[List[str]] = None,
                 client: Optional[httpx.Client] = None) -> QuotaAssessment:
    """주소 → 걸침(C1) + 구통계 + 총량제(C2) 종합."""
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    notes: List[str] = []
    try:
        sv = survey.survey_area(address, radius=radius, ym=ym, client=client)
        applied_hh = sv.applied_hh_total
        infant = gu_hh = None
        facilities = []
        if sv.site_sgg:
            infant = _gu_infant(sv.site_sgg)
            gu_hh = _gu_households(sv.site_sgg)
            try:
                loc = kakao.resolve_coord(address, client=client)
                facilities = collect_survey_facilities(
                    loc["lat"], loc["lon"], radius, sv.site_sgg,
                    region_name=sv.site_dong, client=client)
            except Exception as e:
                notes.append(f"시설 현황 조사 실패 ({type(e).__name__}) — 목록 생략.")
        if infant is None or gu_hh is None:
            notes.append("구 영유아/세대 조회 실패 — 어린이집 산정은 '확인필요'로 표기.")

        hh_list = new_households if isinstance(new_households, list) else [new_households]
        labels = labels or ([f"획지{i+1}" for i in range(len(hh_list))] if len(hh_list) > 1 else [""])
        cfg = quota.load_config()
        results: List[QuotaResult] = [
            quota.compute_quota(hh, applied_hh, infant_pop=infant, gu_hh=gu_hh,
                                existing_area=existing_area, planned_area=planned_area,
                                label=labels[i] if i < len(labels) else f"획지{i+1}", cfg=cfg)
            for i, hh in enumerate(hh_list)
        ]
        return QuotaAssessment(
            address=address, site_sgg=sv.site_sgg, radius=radius, ym=sv.ym,
            gu_infant=infant, gu_households=gu_hh, survey=sv, facilities=facilities,
            results=results, notes=notes + sv.notes)
    finally:
        if own:
            client.close()
