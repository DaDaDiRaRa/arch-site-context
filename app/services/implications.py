"""함의(implications) 룩업 — 규칙 기반, LLM 없음 (모드 A, P4).

app/data/implications.json 규칙을 facts(수치)에 적용해 '참고' 시사점을 만든다.
함의는 코드/규칙이 만든다 — LLM은 마지막 한 문단만 (절대 원칙 2).
값으로 판단하지 않고 '재료'만 제시 — 좋다/나쁘다 단정 금지 (절대 원칙 5).
설정은 JSON, 코드 아님 — 규칙은 JSON만 고치면 바뀐다 (절대 원칙 7).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_PATH = Path(__file__).resolve().parent.parent / "data" / "implications.json"


def load_rules() -> List[dict]:
    """implications.json 규칙 배열을 읽어 반환. 없으면 빈 리스트."""
    if not _PATH.exists():
        return []
    return json.loads(_PATH.read_text(encoding="utf-8"))


def _get(fact: Any, key: str) -> Any:
    """fact 가 dict 든 pydantic 모델이든 값 추출."""
    if isinstance(fact, dict):
        return fact.get(key)
    return getattr(fact, key, None)


def _passes(value: float, threshold: float, op: str) -> bool:
    if op == ">":
        return value > threshold
    if op == ">=":
        return value >= threshold
    if op == "<":
        return value < threshold
    if op == "<=":
        return value <= threshold
    return False


def derive_implications(
    facts: List[Any], use_type: Optional[str] = None
) -> List[Dict[str, str]]:
    """facts 리스트에 규칙을 적용해 implications 리스트 반환.

    각 규칙 when: {item, op, vs:"national", margin}.
    vs="national" 이면 fact.national_avg 기준 threshold = national ± margin.
    use_type 지정 시 규칙의 use_types 에 포함될 때만 적용 (빈 목록이면 모든 용도).
    반환 항목: {text, basis, tag}.
    """
    rules = load_rules()
    fact_by_item: Dict[str, Any] = {}
    for f in facts:
        item = _get(f, "item")
        if item is not None:
            fact_by_item[item] = f

    out: List[Dict[str, str]] = []
    for rule in rules:
        uses = rule.get("use_types") or []
        if use_type is not None and uses and use_type not in uses:
            continue

        when = rule.get("when", {})
        item = when.get("item")
        fact = fact_by_item.get(item)
        if fact is None:
            continue  # 해당 지표 fact 없으면 건너뜀 (확인 불가 → 멈춤, 절대 원칙 3)

        value = _get(fact, "value")
        if value is None:
            continue

        vs = when.get("vs", "national")
        base = _get(fact, "national_avg") if vs == "national" else None
        if base is None:
            continue  # 비교 기준 없으면 추정 안 함

        op = when.get("op", ">")
        margin = float(when.get("margin", 0))
        threshold = base + margin if op in (">", ">=") else base - margin

        if _passes(float(value), threshold, op):
            out.append(
                {
                    "text": rule.get("then", ""),
                    "basis": item,
                    "tag": rule.get("tag", "참고"),
                }
            )
    return out
