"""P9 후보지 비교 오케스트레이션 — 여러 대지를 한 번에 A·B·P11로 읽어 나란히.

기존 서비스를 재사용하되 후보지당 resolve 1회 + 시설검색 1회로 중복 호출을 없앤다
(B 표시 시설종류 ∪ 수급진단 공급종류를 한 번에 검색해 둘이 공용).
한 후보지 실패는 격리(error 필드) — 나머지는 계속. 종합점수 없음, 정렬은 프론트(절대 원칙 5).
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

import httpx

from app.schemas.compare import CompareResult, CompareSite
from app.schemas.region import Fact, Region
from app.schemas.diagnose import Diagnosis
from app.services import diagnose, stats
from app.services.cache import Cache
from app.services.facilities import build_facility_result
from app.services.resolve import resolve_address


def gather_bundle(
    address: str,
    use_type: str,
    radius: int,
    kinds: List[str],
    client: httpx.Client,
    cache: Optional[Cache] = None,
) -> dict:
    """한 주소의 A·B·P11 번들 구성 (후보지 비교·물어보기 공용).

    resolve 1회 + 시설검색 1회로 중복 호출 없음. 실패 시 예외를 그대로 던진다
    (호출부가 격리/ErrorBlock 결정). 반환: region·facts·counts·diagnoses·notes.
    """
    loc = resolve_address(address, client=client)
    if not loc.sgg_code:
        raise ValueError("시군구 코드를 확인할 수 없습니다.")

    notes: List[str] = list(loc.notes)
    rules = diagnose.load_rules()

    # A 지역 통계
    facts, anotes, _ = stats.collect_facts(
        loc.sgg_code, use_type, cache=cache, sigungu=loc.sigungu
    )
    notes += anotes

    # P11 수요지표 (규칙들의 demand_item — 용도와 무관하게 확보)
    demand_items = list(dict.fromkeys(r["demand_item"] for r in rules))
    dfacts, dnotes, _ = stats.collect_facts_by_items(
        loc.sgg_code, demand_items, sigungu=loc.sigungu, cache=cache
    )
    notes += dnotes

    # B 시설검색 1회 — 표시 종류 ∪ 수급진단 공급종류 (loc 재사용으로 재해석 없음)
    supply_kinds = [k for r in rules for k in r["supply_kinds"]]
    all_kinds = list(dict.fromkeys(list(kinds) + supply_kinds))
    fres = build_facility_result(address, all_kinds, [radius], client=client, loc=loc)
    band = fres.counts.get(str(radius), {})
    notes += [n for n in fres.notes if n not in notes]

    # B 표시는 사용자가 고른 kinds 만 (검색은 합집합으로 했어도)
    counts = {k: int(band.get(k, 0)) for k in kinds}

    # P11 교차 (순수 로직 재사용)
    diagnoses, cnotes = diagnose.cross_rules(
        {f["item"]: f for f in dfacts}, band, radius, rules
    )
    notes += cnotes

    return {
        "address": loc.address or address,
        "region": Region(
            name=loc.sigungu or loc.sgg_code, code=loc.sgg_code, resolution="시군구"
        ),
        "facts": facts,        # dict 리스트 (Fact 변환은 호출부에서)
        "counts": counts,
        "diagnoses": diagnoses,
        "notes": notes,
    }


def _build_site(
    address: str,
    use_type: str,
    radius: int,
    kinds: List[str],
    client: httpx.Client,
    cache: Optional[Cache],
) -> CompareSite:
    """후보지 1곳 — 실패해도 예외를 삼켜 error 로 표시(나머지 후보지 보호)."""
    try:
        b = gather_bundle(address, use_type, radius, kinds, client, cache)
        return CompareSite(
            address=b["address"],
            region=b["region"],
            facts=[Fact(**f) for f in b["facts"]],
            counts=b["counts"],
            diagnoses=b["diagnoses"],
            notes=b["notes"],
        )
    except Exception as e:  # 한 후보지 실패가 전체를 막지 않도록 격리 (정직하게 error 표시)
        return CompareSite(address=address, error=str(e))


def build_comparison(
    addresses: List[str],
    use_type: str = "주거",
    radius: int = 1000,
    kinds: Optional[List[str]] = None,
    cache: Optional[Cache] = None,
) -> CompareResult:
    """후보지 목록을 비교 결과로 구성."""
    kinds = kinds or []
    client = httpx.Client(timeout=15.0)
    try:
        sites = [_build_site(a, use_type, radius, kinds, client, cache) for a in addresses]
    finally:
        client.close()
    return CompareResult(
        use_type=use_type,
        radius=radius,
        kinds=kinds,
        sites=sites,
        base_date=date.today().isoformat(),
    )
