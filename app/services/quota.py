"""C2 — 주민공동시설 총량제 산정 엔진 (CLAUDE.md §8.13 심의 현황팩).

서울시 통합심의 '커뮤니티 설치계획(총량제) 검토' 박스를 코드로 재현.
- 규칙(tier·계수·법정면적)은 community_quota.json 만 고치면 바뀐다 (절대 원칙 7).
- 값은 코드 산수, LLM 0 · 새 숫자 안 만듦 (절대 원칙 1·2).
- ⚠ 법정면적은 조례 변동값 — tier confidence 를 결과에 실어 투명하게, low 면 note 로 조례 확인 유도.
- 판정(부족/충족)은 '참고' — 최종 확정은 사람 (절대 원칙 5).

입력 출처: 신축세대=설계입력, 적용세대=C1 걸침합산(services.survey), 구 영유아·세대=KOSIS/jumin,
          기존시설면적=조사입력, 계획면적=설계입력.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from app.schemas.quota import FacilityQuota, QuotaResult

_PATH = Path(__file__).resolve().parent.parent / "data" / "community_quota.json"


def load_config() -> dict:
    """community_quota.json. 없으면 빈 설정."""
    if not _PATH.exists():
        return {"facilities": [], "total_quota": {"tiers": []}}
    return json.loads(_PATH.read_text(encoding="utf-8"))


def _pick_tier(tiers: List[dict], hh: int) -> Optional[dict]:
    """세대규모(hh)에 해당하는 tier. hh_max=null 은 상한 없음. 없으면 None."""
    for t in tiers:
        lo = t.get("hh_min", 0)
        hi = t.get("hh_max")
        if hh >= lo and (hi is None or hh < hi):
            return t
    return None


def _eval_legal(tier: dict, hh: int) -> Optional[float]:
    """tier 의 법정면적 산정. fixed value 또는 구조화 formula. 공공개방 보너스 반영."""
    if tier is None:
        return None
    val: Optional[float]
    if "formula" in tier and isinstance(tier["formula"], dict):
        f = tier["formula"]
        base = f.get("base", 0.0)
        val = base + f.get("per_over", 0.0) * max(0, hh - f.get("over", 0))
    elif tier.get("value") is not None:
        val = float(tier["value"])
    else:
        return None  # 필수 아님/미확정
    bonus = tier.get("public_open_bonus")
    if bonus:
        val = val * bonus
    return round(val, 2)


def _demand_area(demand: dict, new_hh: int, applied_hh: int,
                 infant_pop: Optional[int], gu_hh: Optional[int],
                 existing_area: float):
    """심의검토 산출면적(예상인원 방식). (예상인원, 산출면적) 반환. 산정불가면 (None, None)."""
    if not demand:
        return None, None
    p = demand.get("params", {})
    hh = (new_hh + applied_hh) if demand.get("households") == "new_plus_applied" else applied_hh
    typ = demand.get("type")
    if typ == "per_household_rate":
        exp = hh * p["multiplier"] * p["use_rate"]
        return round(exp, 2), round(exp * p["area_per_person"] - existing_area, 2)
    if typ == "linear_household":
        return None, round(p["base"] + p["per_household"] * hh - existing_area, 2)
    if typ == "infant_rate":
        if not infant_pop or not gu_hh:
            return None, None  # 영유아/구세대 없으면 산정 불가 (추정 안 함, 절대 원칙 3)
        exp = (infant_pop / gu_hh) * hh * p["attendance_rate"]
        return round(exp, 2), round(exp * p["area_per_person"] - existing_area, 2)
    return None, None


def compute_facility(rule: dict, new_hh: int, applied_hh: int,
                     infant_pop: Optional[int] = None, gu_hh: Optional[int] = None,
                     existing_area: float = 0.0,
                     planned_area: Optional[float] = None) -> FacilityQuota:
    """시설 1개 산정. tier 는 신축세대(new_hh) 기준 선택."""
    notes: List[str] = []
    tier = _pick_tier(rule.get("legal_min_tiers", []), new_hh)
    legal = _eval_legal(tier, new_hh)
    conf = tier.get("confidence") if tier else None
    if tier and tier.get("note"):
        notes.append(tier["note"])
    if tier is None:
        notes.append(f"세대규모 {new_hh}에 해당하는 tier 미등록 — 조례 확인 필요.")
    elif legal is None:
        notes.append("이 세대규모는 법정 설치 대상 아님(또는 미확정) — 조례 확인.")
    elif conf == "low":
        notes.append("⚠ 이 tier 법정면적은 조례 변동 관측값(confidence=low) — 해당 심의 조례 확인 필요.")

    exp, req = _demand_area(rule.get("demand", {}), new_hh, applied_hh,
                            infant_pop, gu_hh, existing_area)

    if req is not None:
        verdict = "부족시설" if req > 0 else "충족시설"
    elif rule.get("demand"):
        verdict = "확인필요"  # 산정에 필요한 입력(영유아 등) 없음
        notes.append("산출면적 계산 입력 부족(예: 구 영유아/세대) — 확인 필요.")
    else:
        verdict = "면적기준"

    plan_ok = plan_diff = None
    if planned_area is not None and legal is not None:
        plan_ok = planned_area >= legal
        plan_diff = round(planned_area - legal, 2)

    return FacilityQuota(
        name=rule["name"], households=(new_hh + applied_hh)
        if rule.get("demand", {}).get("households") == "new_plus_applied" else applied_hh,
        expected_people=exp, required_area=req, existing_area=existing_area,
        planned_area=planned_area, legal_min=legal, legal_min_confidence=conf,
        verdict=verdict, plan_ok=plan_ok, plan_diff=plan_diff, notes=notes,
    )


def _total_quota(cfg: dict, hh: int) -> Optional[float]:
    """주민공동시설 합계 총량(㎡) — 참고. 세대규모 tier 별 계수."""
    tier = _pick_tier(cfg.get("total_quota", {}).get("tiers", []), hh)
    if not tier:
        return None
    f = tier.get("formula", {})
    val = (f.get("base", 0.0) + f.get("per_hh", 0.0) * hh) * f.get("mult", 1.0)
    return round(val, 2)


def compute_quota(new_hh: int, applied_hh: int, *,
                  infant_pop: Optional[int] = None, gu_hh: Optional[int] = None,
                  existing_area: Optional[Dict[str, float]] = None,
                  planned_area: Optional[Dict[str, float]] = None,
                  label: str = "", cfg: Optional[dict] = None) -> QuotaResult:
    """한 획지(단지)의 총량제 검토. existing/planned 는 {시설명: ㎡} dict (조사/설계 입력)."""
    cfg = cfg or load_config()
    existing_area = existing_area or {}
    planned_area = planned_area or {}
    facilities = [
        compute_facility(rule, new_hh, applied_hh, infant_pop, gu_hh,
                         existing_area.get(rule["name"], 0.0),
                         planned_area.get(rule["name"]))
        for rule in cfg.get("facilities", [])
    ]
    return QuotaResult(
        label=label, new_households=new_hh, applied_households=applied_hh,
        facilities=facilities, total_quota_area=_total_quota(cfg, new_hh + applied_hh),
    )
