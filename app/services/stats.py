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
    resolution: str = "시군구",
    hcode: str = "",
    hdong: str = "",
) -> Tuple[List[dict], List[str], Optional[int]]:
    """(facts, notes, year) 반환. facts 비어있으면 라우터가 ErrorBlock 처리.

    sigungu: census 계열 지역코드 역추출 + 에어코리아 측정소 검색용.
    sido: 에어코리아 측정소 검색 폴백용.
    resolution: '읍면동'이면 동 데이터 있는 테이블(matrix dong_tables)만 hcode로 조회,
                나머지는 시군구로 폴백(note). hcode/hdong: 행정동 H코드(10자리)·행정동명.
    """
    items = matrix.list_items(use_type)
    if items is None:
        return [], [f"알 수 없는 용도: {use_type}"], None
    return _facts_from_items(
        items, sgg_code, year, cache, sigungu, sido, resolution, hcode, hdong
    )


def collect_facts_by_items(
    sgg_code: str,
    item_names: List[str],
    *,
    sigungu: str = "",
    sido: str = "",
    year: Optional[int] = None,
    cache: Optional[Cache] = None,
    resolution: str = "시군구",
    hcode: str = "",
    hdong: str = "",
) -> Tuple[List[dict], List[str], Optional[int]]:
    """이름으로 지정한 지표들의 facts 수집 (용도 무관 — P11 수급진단 demand용).

    matrix.json 전체에서 이름이 일치하는 항목을 찾아(이름당 첫 매치) 재사용한다.
    matrix 에 없거나 미확정인 지표는 추정 않고 notes 에 정직하게 기록 (절대 원칙 3).
    resolution/hcode/hdong: collect_facts 와 동일 (읍면동 해상도 지원).
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

    facts, fnotes, year_used = _facts_from_items(
        items, sgg_code, year, cache, sigungu, sido, resolution, hcode, hdong
    )
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
    facts, notes = _collect_airkorea_facts(airkorea_items, sido, sigungu, cache)
    # 대기질은 측정소(시군구) 기준 — 모든 수치에 기준 명시 (절대 원칙 4)
    gu_name = sigungu or sido
    for f in facts:
        f.setdefault("scope", gu_name)
        f.setdefault("scope_level", "시군구")
    return facts, notes


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
    resolution: str = "시군구",
    hcode: str = "",
    hdong: str = "",
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
        kosis_items, sgg_code, year, cache, sigungu, resolution, hcode, hdong
    )
    facts.extend(kosis_facts)
    notes.extend(kosis_notes)

    # 에어코리아 (용도별 항목에 직접 포함된 경우) — 측정소 기반, 항상 시군구
    if airkorea_items:
        ak_facts, ak_notes = _collect_airkorea_facts(airkorea_items, sido, sigungu, cache)
        facts.extend(ak_facts)
        notes.extend(ak_notes)
        if resolution == "읍면동" and ak_facts:
            notes.append(f"대기질: 동 단위 측정 없음 → {sigungu or sgg_code} 기준.")

    # scope 기본값 채우기 — KOSIS 외(에어코리아 등)는 시군구 기준 (절대 원칙 4)
    gu_name = sigungu or sgg_code
    for f in facts:
        f.setdefault("scope", gu_name)
        f.setdefault("scope_level", "시군구")

    return facts, notes, year_used


def _collect_kosis_facts(
    items: List[dict],
    sgg_code: str,
    year: Optional[int],
    cache: Optional[Cache],
    sigungu: str,
    resolution: str = "시군구",
    hcode: str = "",
    hdong: str = "",
) -> Tuple[List[dict], List[str], Optional[int]]:
    """KOSIS 항목 → facts + notes + 사용된 연도.

    resolution='읍면동' + hcode 있음 + 테이블이 dong_tables(검증된 reg-scheme)면 행정동 코드로
    조회해 동 단위 값을 만든다. 그 외(census·미검증 테이블)는 시군구로 폴백하고 note (절대 원칙 3·4).
    """
    groups: dict = {}
    notes: List[str] = []
    for it in items:
        k = it["kosis"]
        gk = (k["orgId"], k["tblId"], k.get("objL2"), it.get("region_scheme", "reg"))
        groups.setdefault(gk, []).append(it)

    want_dong = resolution == "읍면동" and bool(hcode)
    dong_set = matrix.dong_tables()
    gu_name = sigungu or sgg_code
    dong_name = hdong or "행정동"

    facts: List[dict] = []
    year_used: Optional[int] = year

    for (org_id, tbl_id, obj_l2, scheme), grp in groups.items():
        # 이 그룹이 동 단위로 갈 수 있는가: 동 요청 + reg-scheme + 검증된 테이블
        group_dong = want_dong and scheme == "reg" and tbl_id in dong_set
        if group_dong:
            region_code = hcode
            scope_name, scope_level = dong_name, "읍면동"
        elif scheme == "census":
            region_code = kosis.resolve_census_region(
                org_id, tbl_id, sgg_code[:2], sigungu, obj_l2=obj_l2, cache=cache
            )
            if not region_code:
                names = ", ".join(it["item"] for it in grp)
                notes.append(f"'{names}': census 지역코드 미확인({sigungu}) — 건너뜀.")
                continue
            scope_name, scope_level = gu_name, "시군구"
        else:
            region_code = sgg_code
            scope_name, scope_level = gu_name, "시군구"

        # 동 요청인데 동으로 못 간 그룹은 정직하게 폴백 사유 표기 (절대 원칙 3·4)
        if want_dong and not group_dong:
            names = ", ".join(it["item"] for it in grp)
            notes.append(f"'{names}': 동 단위 데이터 없음 → {gu_name} 기준.")

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
                    "scope": scope_name,
                    "scope_level": scope_level,
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
