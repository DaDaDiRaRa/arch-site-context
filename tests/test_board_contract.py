"""T 시리즈 2단계 — /board 공유 계약 테스트 (네트워크 불필요).

board_brief(제안서·MCP용 압축 투영)와 board_to_project_seed(세 앱 봉투)를 검증한다.
brief 는 해석 층만 남기고 원시 seed context 는 걷어낸다(경량). project_seed 는 law·knowledge
슬롯을 형제앱에 남긴다. schema_version 으로 소비자가 guard.
"""

from __future__ import annotations

from app.schemas.board import BoardResult, DomainCoverage
from app.schemas.design_drivers import DesignDriver, DriverEvidence
from app.schemas.project_seed import Site
from app.schemas.region import Fact
from app.services.board_contract import board_brief, board_to_project_seed


def _board():
    return BoardResult(
        site=Site(address="서울 영등포구 여의대로 24", lat=37.52, lon=126.92,
                  pnu="1156011000", sgg_code="11560", sido="서울",
                  sigungu="영등포구", eupmyeondong="여의도동"),
        use_type="주거", radius=1000, resolution="시군구",
        facts=[Fact(item="1인가구비율", value=45.1, national_avg=36.1, unit="%",
                    source_tbl="DT_1JC1511", year=2024, scope="영등포구", scope_level="시군구")],
        design_drivers=[DesignDriver(rank=1, name="방재·침수 대비", response="방수판·전기실 검토",
                                     strength=5.0, evidence=[DriverEvidence(key="홍수 위험", detail="영향범위 포함", proximity="읍면동")])],
        coverage=[DomainCoverage(domain="인구", available=True, detail="1개 지표")],
        context={"stores": {"total": 5922}, "schools": [1, 2, 3], "notes": ["..."]},  # 원시 — brief 에서 빠져야
        base_date="2026-07-09",
    )


def test_schema_versions() -> None:
    b = _board()
    assert b.schema_version == "board/1.0"
    seed = board_to_project_seed(b)
    assert seed.schema_version == "project_seed/1.0"


def test_brief_strips_raw_context_keeps_interpretation() -> None:
    brief = board_brief(_board())
    assert brief["schema_version"] == "board_brief/1.0"
    # 원시 seed context(상권 수천건)는 빠진다
    assert "context" not in brief
    assert "stores" not in brief
    # 해석 층은 보존
    assert brief["design_drivers"][0]["name"] == "방재·침수 대비"
    assert brief["key_facts"][0]["index"] == 125  # 45.1/36.1×100
    assert brief["site"]["sigungu"] == "영등포구"


def test_brief_is_smaller_than_full() -> None:
    import json
    b = _board()
    full = len(json.dumps(b.model_dump(), ensure_ascii=False, default=str))
    brief = len(json.dumps(board_brief(b), ensure_ascii=False, default=str))
    assert brief < full  # 투영이 더 작다 (여기선 작은 픽스처지만 원시 context 제거로 축소)


def test_project_seed_leaves_sibling_slots() -> None:
    seed = board_to_project_seed(_board(), law={"far": 940}, knowledge=None)
    assert seed.site.sgg_code == "11560"
    assert seed.law == {"far": 940}       # 형제앱 주입
    assert seed.knowledge is None         # 빈 슬롯
    assert "design_drivers" in seed.context  # 터읽기 블록 전체


def test_brief_accepts_dict_and_model() -> None:
    b = _board()
    from_model = board_brief(b)
    from_dict = board_brief(b.model_dump())
    assert from_model["design_drivers"] == from_dict["design_drivers"]
