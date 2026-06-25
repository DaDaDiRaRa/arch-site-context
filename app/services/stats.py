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

    if method == "ratio":
        # 같은 분류(objL2_pick) 안에서 두 itmId의 비율 ×100 (예: 1인가구/일반가구).
        c2 = k.get("objL2_pick", "0")
        num = _direct(rows, k.get("num_itm"), c2)
        den = _direct(rows, k.get("den_itm"), c2)
        if num is None or not den:
            return None
        return round(num / den * 100, 1)

    return None  # unconfirmed 등


def collect_facts(
    sgg_code: str,
    use_type: str,
    year: Optional[int] = None,
    cache: Optional[Cache] = None,
    *,
    sigungu: str = "",
) -> Tuple[List[dict], List[str], Optional[int]]:
    """(facts, notes, year) 반환. facts 비어있으면 라우터가 ErrorBlock 처리.

    sigungu: 시군구명 (census 계열 테이블의 지역코드 역추출용 — 행안부코드와 다름).
    """
    items = matrix.list_items(use_type)
    if items is None:
        return [], [f"알 수 없는 용도: {use_type}"], None
    return _facts_from_items(items, sgg_code, year, cache, sigungu)


def collect_facts_by_items(
    sgg_code: str,
    item_names: List[str],
    *,
    sigungu: str = "",
    year: Optional[int] = None,
    cache: Optional[Cache] = None,
) -> Tuple[List[dict], List[str], Optional[int]]:
    """이름으로 지정한 지표들의 facts 수집 (용도 무관 — P11 수급진단 demand용).

    matrix.json 전체에서 이름이 일치하는 항목을 찾아(이름당 첫 매치) 재사용한다.
    matrix 에 없거나 미확정인 지표는 추정 않고 notes 에 정직하게 기록 (절대 원칙 3).
    """
    all_by_ut = matrix.list_items()  # {용도: [항목...]}
    by_name: dict[str, dict] = {}
    for ut_items in all_by_ut.values():
        for it in ut_items:
            by_name.setdefault(it["item"], it)

    items: List[dict] = []
    notes: List[str] = []
    for name in item_names:
        it = by_name.get(name)
        if it is None:
            notes.append(f"'{name}': matrix.json 에 정의 없음 — 건너뜀.")
            continue
        items.append(it)

    facts, fnotes, year_used = _facts_from_items(items, sgg_code, year, cache, sigungu)
    return facts, notes + fnotes, year_used


def _facts_from_items(
    items: List[dict],
    sgg_code: str,
    year: Optional[int],
    cache: Optional[Cache],
    sigungu: str,
) -> Tuple[List[dict], List[str], Optional[int]]:
    """항목 리스트 → facts. 용도별/이름별 진입점이 공유하는 KOSIS 수집 코어."""
    # (orgId,tblId,objL2,지역체계) 로 그룹화 → 그룹당 지역 1콜 + 전국 1콜
    groups: dict[Tuple[str, str, Optional[str], str], List[dict]] = {}
    notes: List[str] = []
    for it in items:
        if it.get("method") in (None, "unconfirmed") or not it.get("kosis"):
            notes.append(f"'{it['item']}': KOSIS 테이블 미확정 — 건너뜀 (추정 금지).")
            continue
        k = it["kosis"]
        gk = (k["orgId"], k["tblId"], k.get("objL2"), it.get("region_scheme", "reg"))
        groups.setdefault(gk, []).append(it)

    facts: List[dict] = []
    year_used: Optional[int] = year
    for (org_id, tbl_id, obj_l2, scheme), grp in groups.items():
        # census 계열은 행안부 시군구코드를 못 쓰므로 테이블 지역목록에서 역추출.
        if scheme == "census":
            region_code = kosis.resolve_census_region(
                org_id, tbl_id, sgg_code[:2], sigungu, obj_l2=obj_l2, cache=cache
            )
            if not region_code:
                names = ", ".join(it["item"] for it in grp)
                notes.append(f"'{names}': census 지역코드 미확인({sigungu}) — 건너뜀.")
                continue
        else:
            region_code = sgg_code
        try:
            reg = kosis.fetch_table(org_id, tbl_id, region_code, year, obj_l2=obj_l2, cache=cache)
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
