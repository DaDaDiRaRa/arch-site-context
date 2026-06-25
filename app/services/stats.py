"""통계 조립 — matrix 항목을 KOSIS로 채워 facts[] 생성 (모드 A, P5).

흐름: sgg_code → 항목을 (orgId,tblId,objL2)로 묶어 KOSIS 1회씩 호출(지역+전국)
      → 레시피(method)로 값 계산 → Fact{item,value,national_avg,unit,source_tbl,year}.
숫자는 코드/규칙이 만든다 (절대 원칙 2). 확정 못한 항목은 추정 않고 건너뛴다 (절대 원칙 3).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.services import kosis, matrix
from app.services.cache import Cache

_NATIONAL = "00"  # KOSIS 전국 코드


def _age_start(c2: Optional[str]) -> Optional[int]:
    """연령밴드 코드(C2) → 밴드 시작나이. '0'(계)·비숫자는 None.

    C2: '5'=0-4세 … '70'=65-69세 … '105'=100+ → 시작나이 = int(c2) - 5.
    """
    if not c2 or c2 == "0" or not c2.isdigit():
        return None
    return int(c2) - 5


def _direct(rows: List[dict], itm_id: str, c2: str = "0") -> Optional[float]:
    for r in rows:
        if r["itm_id"] == itm_id and (r["c2"] == c2 or (c2 == "0" and r["c2"] in ("0", None))):
            return r["value"]
    return None


def _age_total(rows: List[dict], itm_id: str) -> Optional[float]:
    return _direct(rows, itm_id, "0")


def _age_sum(rows: List[dict], itm_id: str, age_min: int, age_max: Optional[int]) -> float:
    s = 0.0
    for r in rows:
        if r["itm_id"] != itm_id or r["value"] is None:
            continue
        start = _age_start(r["c2"])
        if start is None:
            continue
        if start >= age_min and (age_max is None or start <= age_max):
            s += r["value"]
    return s


def _whole_to_int(v: Optional[float]):
    """정수형 카운트(예: 총인구수)는 int 로 — facts·AI 문단에 '.0' 안 붙게."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _compute(item: dict, rows: List[dict]) -> Optional[float]:
    """matrix 항목의 method 레시피로 값 계산. 불가하면 None."""
    method = item.get("method")
    k = item.get("kosis", {})
    itm_id = k.get("itmId", "T2")

    if method == "direct":
        v = _direct(rows, itm_id, k.get("objL2_pick", "0"))
        return v

    if method == "age_share":
        total = _age_total(rows, itm_id)
        if not total:
            return None
        num = _age_sum(rows, itm_id, item.get("age_min", 0), item.get("age_max"))
        return round(num / total * 100, 1)

    if method == "age_dependency":
        old = _age_sum(rows, itm_id, item.get("age_old_min", 65), None)
        work = _age_sum(rows, itm_id, item.get("work_min", 15), item.get("work_max", 64))
        if not work:
            return None
        return round(old / work * 100, 1)

    return None  # unconfirmed 등


def collect_facts(
    sgg_code: str,
    use_type: str,
    year: Optional[int] = None,
    cache: Optional[Cache] = None,
) -> Tuple[List[dict], List[str], Optional[int]]:
    """(facts, notes, year) 반환. facts 비어있으면 라우터가 ErrorBlock 처리."""
    items = matrix.list_items(use_type)
    if items is None:
        return [], [f"알 수 없는 용도: {use_type}"], None

    # (orgId,tblId,objL2) 로 그룹화 → 그룹당 지역 1콜 + 전국 1콜
    groups: dict[Tuple[str, str, Optional[str]], List[dict]] = {}
    notes: List[str] = []
    for it in items:
        if it.get("method") in (None, "unconfirmed") or not it.get("kosis"):
            notes.append(f"'{it['item']}': KOSIS 테이블 미확정 — 건너뜀 (추정 금지).")
            continue
        k = it["kosis"]
        gk = (k["orgId"], k["tblId"], k.get("objL2"))
        groups.setdefault(gk, []).append(it)

    facts: List[dict] = []
    year_used: Optional[int] = year
    for (org_id, tbl_id, obj_l2), grp in groups.items():
        try:
            reg = kosis.fetch_table(org_id, tbl_id, sgg_code, year, obj_l2=obj_l2, cache=cache)
            nat = kosis.fetch_table(org_id, tbl_id, _NATIONAL, reg["year"], obj_l2=obj_l2, cache=cache)
        except kosis.KosisError as e:
            notes.append(f"테이블 {tbl_id} 조회 실패: {e}")
            continue
        year_used = reg["year"]
        for it in grp:
            value = _whole_to_int(_compute(it, reg["rows"]))
            nat_val = _whole_to_int(_compute(it, nat["rows"]))
            if value is None:
                notes.append(f"'{it['item']}': 값 계산 불가 — 건너뜀.")
                continue
            facts.append(
                {
                    "item": it["item"],
                    "value": value,
                    "national_avg": nat_val,
                    "unit": it.get("unit", ""),
                    "source_tbl": tbl_id,
                    "year": reg["year"],
                }
            )
    return facts, notes, year_used
