"""T3 — 프로그램 함의(POR) 엔진 (CLAUDE.md §8.12).

통합 풀을 program_rules.json 규칙과 매칭해 **건축 카테고리별 공간·프로그램 권고**를 방출한다.
"이 맥락이니 무엇을, 어느 카테고리에" = Program of Requirements 체크리스트.

절 매칭(AND)·근거 추출은 S2 `cross_context._eval_clause` 를 **그대로 재사용**(중복 0). 다른 점은
출력 — S2 는 도메인 횡단 prose 시사점, T3 는 카테고리별 권고 항목. **LLM 0·새 숫자 0**(원칙 1·2).
카테고리+권고 중복은 병합(basis 합침). 카테고리 순서로 정렬.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

from app.schemas.program import ProgramItem
from app.services.cross_context import _eval_clause, _get

_PATH = Path(__file__).resolve().parent.parent / "data" / "program_rules.json"


def _load() -> dict:
    if not _PATH.exists():
        return {}
    return json.loads(_PATH.read_text(encoding="utf-8"))


def derive_program(
    facts: Optional[List[Any]] = None,
    diagnoses: Optional[List[Any]] = None,
    hazards: Any = None,
    use_type: Optional[str] = None,
) -> List[ProgramItem]:
    """통합 풀 → 카테고리별 프로그램 권고. 규칙 when 이 모두 참일 때만 items 방출."""
    facts = facts or []
    diagnoses = diagnoses or []
    rules = _load()

    fact_by_item = {_get(f, "item"): f for f in facts if _get(f, "item")}
    diag_by_name = {_get(d, "name"): d for d in diagnoses if _get(d, "name")}

    from app.services.matrix import resolve_profile
    profile = resolve_profile(use_type) if use_type is not None else None  # 법적 용도 → 프로파일 (2계층)
    # (category, recommendation) → basis 집합 (병합·순서 보존)
    merged: dict = {}
    order: List[tuple] = []
    for rule in rules.get("rules", []):
        uses = rule.get("use_types") or []
        if profile is not None and uses and profile not in uses:
            continue
        clauses = rule.get("when") or []
        if not clauses:
            continue
        ok = True
        basis: List[str] = []
        for clause in clauses:
            matched, b = _eval_clause(clause, fact_by_item, diag_by_name, hazards)
            if not matched:
                ok = False
                break
            if b is not None and _get(b, "key") not in basis:
                basis.append(_get(b, "key"))
        if not ok:
            continue
        for item in rule.get("items", []):
            k = (item.get("category", ""), item.get("recommendation", ""))
            if k not in merged:
                merged[k] = []
                order.append(k)
            for bkey in basis:
                if bkey not in merged[k]:
                    merged[k].append(bkey)

    if not merged:
        return []

    cats = rules.get("categories", [])
    cat_rank = {c: i for i, c in enumerate(cats)}
    orig = {k: i for i, k in enumerate(order)}  # 삽입 순서 고정 (정렬 중 index() 금지)
    order.sort(key=lambda k: (cat_rank.get(k[0], len(cats)), orig[k]))
    return [ProgramItem(category=cat, recommendation=rec, basis=merged[(cat, rec)], tag="참고")
            for (cat, rec) in order]
