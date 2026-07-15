"""용도별 항목 매트릭스 로더 (모드 A, P4).

app/data/matrix.json 을 읽어 용도(use_type)·우선순위(min_priority)로 항목을 거른다.
설정은 JSON, 코드 아님 — 건축가가 JSON만 고치면 동작이 바뀐다 (절대 원칙 7).
매 호출마다 새로 읽어 편집이 즉시 반영되게 한다 (작은 파일).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

_PATH = Path(__file__).resolve().parent.parent / "data" / "matrix.json"
_MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "use_type_map.json"
_SRC_PATH = Path(__file__).resolve().parent.parent / "data" / "profile_sources.json"


def load_matrix() -> dict:
    """matrix.json 전체를 읽어 반환. 없으면 빈 dict."""
    if not _PATH.exists():
        return {}
    return json.loads(_PATH.read_text(encoding="utf-8"))


def load_use_type_map() -> dict:
    """use_type_map.json (법적 용도 → 분석 프로파일). 없으면 빈 dict."""
    if not _MAP_PATH.exists():
        return {}
    return json.loads(_MAP_PATH.read_text(encoding="utf-8"))


def use_types() -> List[str]:
    """정의된 분석 프로파일 키 목록 ('_' 로 시작하는 메타키 제외)."""
    return [k for k in load_matrix().keys() if not k.startswith("_")]


def resolve_profile(use_type: Optional[str]) -> Optional[str]:
    """입력(분석 프로파일명 또는 법적 용도명) → 분석 프로파일명. 알 수 없으면 None.

    2계층: 프론트는 법적 용도(건축법 별표1)를, 백엔드는 프로파일로 분석한다.
    - 이미 프로파일(matrix 키)이면 그대로.
    - 법적 용도면 use_type_map 으로 매핑.
    - 둘 다 아니면 None (알 수 없는 용도 → 라우터가 하드블록, 절대 원칙 3).
    """
    if not use_type:
        return None
    if use_type in load_matrix():  # 이미 프로파일(또는 _common)
        return use_type
    return load_use_type_map().get("map", {}).get(use_type)


def legal_uses() -> List[str]:
    """매핑된 법적 용도(건축법 별표1) 목록."""
    return list(load_use_type_map().get("map", {}).keys())


def use_type_groups() -> List[dict]:
    """프론트 드롭다운용 그룹핑된 법적 용도 목록."""
    return load_use_type_map().get("groups", [])


def data_limited_uses() -> List[str]:
    """인구통계로 차별화 못 하는 용도(가장 가까운 프로파일 + 캐비엇 표시 대상)."""
    return load_use_type_map().get("data_limited", [])


def load_profile_sources() -> dict:
    """profile_sources.json (P13 — 프로파일별 관련 소스). 없으면 빈 dict."""
    if not _SRC_PATH.exists():
        return {}
    return json.loads(_SRC_PATH.read_text(encoding="utf-8"))


def _relevant(use_type: Optional[str], kind: str) -> Optional[set]:
    """P13 — 프로파일의 관련 소스 집합(kind='seed'|'supply'). 미지정·미등록이면 None(=전체·하위호환)."""
    profile = resolve_profile(use_type)
    if not profile:
        return None
    entry = load_profile_sources().get("profiles", {}).get(profile)
    if not entry or kind not in entry:
        return None
    return set(entry[kind])


def relevant_seed(use_type: Optional[str]) -> Optional[set]:
    """이 용도(프로파일)에 관련된 /seed context 블록 키 집합. None이면 전체(하위호환)."""
    return _relevant(use_type, "seed")


def relevant_supply(use_type: Optional[str]) -> Optional[set]:
    """이 용도(프로파일)에 관련된 /diagnose 수급규칙 이름 집합. None이면 전체(하위호환)."""
    return _relevant(use_type, "supply")


def dong_tables() -> set:
    """읍면동 해상도가 검증된 KOSIS tblId 집합 (_meta.dong_tables).

    resolution='읍면동' 요청 시 이 집합의 reg-scheme 테이블만 행정동 코드로 조회하고,
    나머지는 시군구로 폴백한다 (설정은 JSON — 절대 원칙 7).
    """
    return set(load_matrix().get("_meta", {}).get("dong_tables", []))


def _filter(items: List[dict], min_priority: int) -> List[dict]:
    """priority <= min_priority 항목만, priority 오름차순 정렬."""
    picked = [i for i in items if int(i.get("priority", 99)) <= min_priority]
    return sorted(picked, key=lambda i: int(i.get("priority", 99)))


def list_items(
    use_type: Optional[str] = None, min_priority: int = 3
) -> Optional[object]:
    """항목 목록 반환.

    use_type 지정 시: 해당 용도의 항목 리스트. 모르는 용도면 None.
    미지정 시: {용도: [항목...]} 전체 dict.
    min_priority: 이 값 이하 우선순위(1=필수)만 포함. 기본 3(전체).
    """
    m = load_matrix()
    if use_type is not None:
        items = m.get(use_type)
        if items is None:  # 프로파일 직접 매칭 실패 → 법적 용도일 수 있음 → 프로파일로 해석
            profile = resolve_profile(use_type)
            items = m.get(profile) if profile else None
        if items is None:
            return None  # 알 수 없는 용도 → 라우터가 구분 처리
        return _filter(items, min_priority)
    return {ut: _filter(m[ut], min_priority) for ut in use_types()}
