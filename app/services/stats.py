"""통계 조립 — matrix 항목을 source_type별로 채워 facts[] 생성 (모드 A, P5·P12).

흐름: sgg_code + source_type 디스패처
  - "kosis"(기본 또는 미지정) → KOSIS 1콜/그룹 (지역+전국)
  - "airkorea" / method="realtime" → 에어코리아 일평균 (시군구명 기반)
  - _common 항목은 collect_common_facts()로 별도 수집해 병합 (모든 용도 공통)
숫자는 코드/규칙이 만든다 (절대 원칙 2). 확정 못한 항목은 추정 않고 건너뜀 (절대 원칙 3).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.services import kosis, matrix
from app.services.cache import Cache

_NATIONAL = "00"  # KOSIS 전국 코드


# ─────────────────────────────────────────────────────────────────────────────
# KOSIS 계산 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

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
        return _direct(rows, itm_id, k.get("objL2_pick", "0"))

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
        c2 = k.get("objL2_pick", "0")
        num = _direct(rows, k.get("num_itm"), c2)
        den = _direct(rows, k.get("den_itm"), c2)
        if num is None or not den:
            return None
        return round(num / den * 100, 1)

    return None  # unconfirmed 등


# ─────────────────────────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────────────────────────

def collect_facts(
    sgg_code: str,
    use_type: str,
    year: Optional[int] = None,
    cache: Optional[Cache] = None,
    *,
    sigungu: str = "",
    sido: str = "",
) -> Tuple[List[dict], List[str], Optional[int]]:
    """(facts, notes, year) 반환. facts 비어있으면 라우터가 ErrorBlock 처리.

    sigungu: census 계열 지역코드 역추출 + 에어코리아 측정소 검색용.
    sido: 에어코리아 측정소 검색 폴백용.
    """
    items = matrix.list_items(use_type)
    if items is None:
        return [], [f"알 수 없는 용도: {use_type}"], None
    return _facts_from_items(items, sgg_code, year, cache, sigungu, sido)


def collect_facts_by_items(
    sgg_code: str,
    item_names: List[str],
    *,
    sigungu: str = "",
    sido: str = "",
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

    facts, fnotes, year_used = _facts_from_items(items, sgg_code, year, cache, sigungu, sido)
    return facts, notes + fnotes, year_used


def fetch_total_pop(sgg_code: str, cache: Optional[Cache] = None) -> Optional[int]:
    """시군구 주민등록 총인구수. DT_1B04005N(행안부코드) — 수급진단 밀도 계산용.

    같은 테이블을 age_share 계산에도 쓰므로 캐시 적중 → 추가 API 호출 없음.
    실패 시 None (수급진단이 graceful fallback으로 개수 기반 레벨 사용).
    """
    try:
        result = kosis.fetch_table("101", "DT_1B04005N", sgg_code, None, obj_l2="ALL", cache=cache)
        total = _age_total(result["rows"], "T2")
        return int(total) if total else None
    except Exception:
        return None


def collect_common_facts(
    sido: str,
    sigungu: str,
    cache: Optional[Cache] = None,
) -> Tuple[List[dict], List[str]]:
    """_common 항목(용도 무관) 수집. /analyze 라우터가 결과를 facts[]에 병합한다."""
    common_items = matrix.list_items("_common")
    if not common_items:
        return [], []
    airkorea_items = [it for it in common_items if it.get("source_type") == "airkorea"]
    if not airkorea_items:
        return [], []
    return _collect_airkorea_facts(airkorea_items, sido, sigungu, cache)


# ─────────────────────────────────────────────────────────────────────────────
# 내부 구현
# ─────────────────────────────────────────────────────────────────────────────

def _facts_from_items(
    items: List[dict],
    sgg_code: str,
    year: Optional[int],
    cache: Optional[Cache],
    sigungu: str,
    sido: str = "",
) -> Tuple[List[dict], List[str], Optional[int]]:
    """항목 리스트 → facts. source_type별 디스패처 (P12)."""
    kosis_items: List[dict] = []
    airkorea_items: List[dict] = []
    notes: List[str] = []

    for it in items:
        method = it.get("method")
        if method in (None, "unconfirmed"):
            notes.append(f"'{it['item']}': 데이터 소스 미확정 — 건너뜀 (추정 금지).")
            continue
        st = it.get("source_type", "kosis")
        if st == "airkorea" or method == "realtime":
            airkorea_items.append(it)
        else:
            if not it.get("kosis"):
                notes.append(f"'{it['item']}': KOSIS 테이블 미확정 — 건너뜀.")
                continue
            kosis_items.append(it)

    facts: List[dict] = []

    # KOSIS
    kosis_facts, kosis_notes, year_used = _collect_kosis_facts(
        kosis_items, sgg_code, year, cache, sigungu
    )
    facts.extend(kosis_facts)
    notes.extend(kosis_notes)

    # 에어코리아 (용도별 항목에 직접 포함된 경우)
    if airkorea_items:
        ak_facts, ak_notes = _collect_airkorea_facts(airkorea_items, sido, sigungu, cache)
        facts.extend(ak_facts)
        notes.extend(ak_notes)

    return facts, notes, year_used


def _collect_kosis_facts(
    items: List[dict],
    sgg_code: str,
    year: Optional[int],
    cache: Optional[Cache],
    sigungu: str,
) -> Tuple[List[dict], List[str], Optional[int]]:
    """KOSIS 항목 → facts + notes + 사용된 연도."""
    groups: dict = {}
    notes: List[str] = []
    for it in items:
        k = it["kosis"]
        gk = (k["orgId"], k["tblId"], k.get("objL2"), it.get("region_scheme", "reg"))
        groups.setdefault(gk, []).append(it)

    facts: List[dict] = []
    year_used: Optional[int] = year

    for (org_id, tbl_id, obj_l2, scheme), grp in groups.items():
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
                    "source_type": "kosis",
                }
            )
    return facts, notes, year_used


def _collect_airkorea_facts(
    items: List[dict],
    sido: str,
    sigungu: str,
    cache: Optional[Cache],
) -> Tuple[List[dict], List[str]]:
    """에어코리아 항목 → facts."""
    if not sigungu:
        return [], ["에어코리아: 시군구명 없음 — 건너뜀."]
    from app.services.airkorea import fetch_air_quality
    requested = [it["item"] for it in items]
    return fetch_air_quality(sido, sigungu, requested_items=requested, cache=cache)
