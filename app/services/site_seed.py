"""site 해석 공통화 + project_seed 조립 (INTEGRATION.md §6-1).

주소 → 공유 `Site`(좌표·법정동코드·시군구코드·PNU)를 만드는 단일 진입점.
좌표·행정구역은 resolve_address(카카오/JUSO) 1곳, PNU는 VWorld 개별공시지가에서 보강.
세 앱이 같은 site 를 공유 → 키·호출 중복 제거 (절대 원칙 1·4 일관성).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import httpx

from app.schemas.project_seed import ProjectSeed, Site
from app.services import vworld
from app.services.resolve import resolve_address


def build_site(
    address: str,
    with_pnu: bool = True,
    client: Optional[httpx.Client] = None,
) -> Site:
    """주소 → 공유 Site. PNU 는 best-effort(실패해도 빈 문자열로 진행 — 절대 원칙 3)."""
    own = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        loc = resolve_address(address, client=client)
        pnu = ""
        if with_pnu:
            lp, _ = vworld.fetch_land_price(loc.lon, loc.lat, client=client)
            if lp:
                pnu = lp.get("pnu", "") or ""
        return Site(
            address=loc.address,
            lat=loc.lat,
            lon=loc.lon,
            pnu=pnu,
            bcode=loc.bcode,
            sgg_code=loc.sgg_code,
            sido=loc.sido,
            sigungu=loc.sigungu,
            eupmyeondong=loc.eupmyeondong,
        )
    finally:
        if own:
            client.close()


def build_project_seed(
    address: str,
    context: Optional[dict] = None,
    law: Optional[dict] = None,
    knowledge: Optional[dict] = None,
    with_pnu: bool = True,
    client: Optional[httpx.Client] = None,
    base_date: Optional[str] = None,
) -> ProjectSeed:
    """주소 → ProjectSeed 골격. context/law/knowledge 는 각 앱이 채워 넣는다.

    터읽기는 site + context 를 책임지고, law·knowledge 는 형제 앱이 주입(경계 — §2).
    """
    site = build_site(address, with_pnu=with_pnu, client=client)
    return ProjectSeed(
        site=site,
        context=context,
        law=law,
        knowledge=knowledge,
        base_date=base_date or date.today().isoformat(),
    )
