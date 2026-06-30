"""D1 읍면동 해상도 라우팅 단위테스트 (네트워크 불필요).

resolution='읍면동'일 때 검증된 reg-scheme 테이블(matrix dong_tables)만 행정동 코드로
조회하고, census·미검증 테이블은 시군구로 폴백하며 각 fact 에 scope 가 정직하게 붙는지 검증한다
(절대 원칙 3·4). KOSIS 호출은 monkeypatch 로 대체한다.
"""

from __future__ import annotations

import pytest

from app.services import stats


_POP_ITEM = {
    "item": "총인구수", "method": "direct", "unit": "명",
    "kosis": {"orgId": "101", "tblId": "DT_1B04005N", "itmId": "T2", "objL2": "ALL", "objL2_pick": "0"},
}
_CENSUS_ITEM = {
    "item": "평균가구원수", "method": "direct", "region_scheme": "census", "unit": "명",
    "kosis": {"orgId": "101", "tblId": "DT_1JC1511", "itmId": "T300", "objL2": "000", "objL2_pick": "000"},
}


@pytest.fixture
def fake_kosis(monkeypatch):
    """fetch_table 호출의 (tblId, region_code) 기록 + 합성 행 반환. census 리졸버도 고정."""
    calls: list = []

    def fake_fetch_table(org_id, tbl_id, region_code, year=None, *, itm_id="ALL", obj_l2=None, cache=None):
        calls.append((tbl_id, region_code))
        if tbl_id == "DT_1B04005N":
            rows = [{"itm_id": "T2", "c2": "0", "c2_nm": "계", "value": 34066.0, "unit": "명", "prd_de": "2025"}]
        else:  # DT_1JC1511
            rows = [{"itm_id": "T300", "c2": "000", "c2_nm": "계", "value": 2.0, "unit": "명", "prd_de": "2024"}]
        return {"rows": rows, "year": int(rows[0]["prd_de"])}

    monkeypatch.setattr(stats.kosis, "fetch_table", fake_fetch_table)
    monkeypatch.setattr(stats.kosis, "resolve_census_region", lambda *a, **k: "11190")
    return calls


def test_sigungu_mode_uses_sgg_and_scope(fake_kosis) -> None:
    facts, notes, _ = stats._collect_kosis_facts(
        [_POP_ITEM], "11560", None, None, "영등포구", resolution="시군구"
    )
    assert facts[0]["scope"] == "영등포구"
    assert facts[0]["scope_level"] == "시군구"
    # DT_1B04005N 을 시군구코드(11560)로 조회 (national '00' 도 호출됨)
    assert ("DT_1B04005N", "11560") in fake_kosis


def test_dong_mode_uses_hcode_for_verified_table(fake_kosis) -> None:
    facts, notes, _ = stats._collect_kosis_facts(
        [_POP_ITEM], "11560", None, None, "영등포구",
        resolution="읍면동", hcode="1156054000", hdong="여의동",
    )
    f = facts[0]
    assert f["scope"] == "여의동"
    assert f["scope_level"] == "읍면동"
    # 검증된 테이블은 행정동 H코드로 조회
    assert ("DT_1B04005N", "1156054000") in fake_kosis


def test_dong_mode_falls_back_for_census(fake_kosis) -> None:
    facts, notes, _ = stats._collect_kosis_facts(
        [_CENSUS_ITEM], "11560", None, None, "영등포구",
        resolution="읍면동", hcode="1156054000", hdong="여의동",
    )
    # census 는 동 미지원 → 시군구 폴백 + 정직한 note (절대 원칙 3·4)
    assert facts[0]["scope_level"] == "시군구"
    assert facts[0]["scope"] == "영등포구"
    assert any("동 단위 데이터 없음" in n for n in notes)
    # 행정동 코드(hcode)로는 조회하지 않음 — census 코드(11190)로 조회
    assert not any(rc == "1156054000" for _, rc in fake_kosis)


def test_dong_capable_set_from_matrix() -> None:
    from app.services import matrix
    assert "DT_1B04005N" in matrix.dong_tables()
