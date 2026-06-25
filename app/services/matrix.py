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


def load_matrix() -> dict:
    """matrix.json 전체를 읽어 반환. 없으면 빈 dict."""
    if not _PATH.exists():
        return {}
    return json.loads(_PATH.read_text(encoding="utf-8"))


def use_types() -> List[str]:
    """정의된 용도 키 목록 ('_' 로 시작하는 메타키 제외)."""
    return [k for k in load_matrix().keys() if not k.startswith("_")]


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
        if items is None:
            return None  # 알 수 없는 용도 → 라우터가 구분 처리
        return _filter(items, min_priority)
    return {ut: _filter(m[ut], min_priority) for ut in use_types()}
