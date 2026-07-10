"""한 문단 서술 — Claude 1회 + 규칙 폴백 (모드 A, P6).

facts(수치)·implications(함의)는 코드/룩업이 만든 것. LLM은 '표현만' 담당 (절대 원칙 2).
모델은 Claude 하나 — 교차검증·다중모델 금지 (절대 원칙 6).
프롬프트 엄격: facts 수치만 인용, 해석·의견 금지, '○○구 기준'·연도 명시, 용도 관점.
AI 실패/키없음/타임아웃 → 규칙 기반 템플릿 폴백 (facts·implications는 어느 경우든 보존).
"""

from __future__ import annotations

import os
from typing import List, Tuple

_MODEL = "claude-opus-4-8"
_TIMEOUT_S = 30.0

_SYSTEM = (
    "당신은 건축 대지분석 보조자다. 아래 제공된 통계 facts만 사용해 한국어 한 문단(3~5문장)을 쓴다.\n"
    "규칙(반드시 지킴):\n"
    "1) facts 에 있는 수치만 인용한다. 제공되지 않은 숫자·항목·시설을 절대 만들지 않는다.\n"
    "2) 좋다/나쁘다·사업성·전망·권고 같은 해석·의견·단정을 쓰지 않는다. 사실 서술만 한다.\n"
    "   (implications 는 '참고' 재료일 뿐, 검토 사항으로만 부드럽게 언급하고 단정하지 않는다.)\n"
    "3) 각 수치의 기준 지역(facts 의 [기준:○○] — 행정동 또는 시군구)과 연도를 명시한다. "
    "시군구 평균값은 대지 고유값이 아님을 밝힌다. 기준이 섞여 있으면 어느 지표가 어느 기준인지 구분해 쓴다.\n"
    "4) 건물 용도 관점에서 관련 수치를 자연스럽게 묶는다.\n"
    "5) 한 문단으로만. 머리말·목록·제목 없이 문단 텍스트만 출력한다."
)


def _facts_block(facts: List[dict]) -> str:
    lines = []
    for f in facts:
        na = f.get("national_avg")
        unit = f.get("unit", "")
        # 비율(%) 지표만 전국 비교 의미 있음 — 절대수는 전국 총량과 비교 무의미 (AI 가 "전국보다 낮다" 쓰지 않도록)
        na_txt = f"전국 {na}{unit}" if (na is not None and unit == "%") else "전국 비교 해당없음"
        scope = f.get("scope")
        scope_txt = f" [기준:{scope}]" if scope else ""
        lines.append(
            f"- {f['item']}: {f['value']}{f.get('unit','')} ({na_txt}){scope_txt} "
            f"[{f.get('source_tbl')} {f.get('year')}]"
        )
    return "\n".join(lines)


def _imps_block(imps: List[dict]) -> str:
    if not imps:
        return "(없음)"
    return "\n".join(f"- {i['text']} (근거: {i.get('basis')})" for i in imps)


def _scope_disclaimer(facts: List[dict]) -> str:
    """facts 의 scope 구성에 맞는 정직한 기준 안내 (절대 원칙 4).

    반경·동·구 혼재 시 어느 지표가 어느 기준인지 밝힌다. scope 없으면(구버전) 시군구로 간주.
    """
    radius = sorted({f.get("scope") for f in facts if f.get("scope_level") == "반경" and f.get("scope")})
    dong = sorted({f.get("scope") for f in facts if f.get("scope_level") == "읍면동" and f.get("scope")})
    gu = sorted({f.get("scope") for f in facts
                 if f.get("scope_level") not in ("반경", "읍면동") and f.get("scope")})
    parts: List[str] = []
    if radius:
        parts.append(f"{', '.join(radius)}는 반경 내 추계 실인구")
    if dong:
        parts.append(f"{', '.join(dong)}는 행정동 단위")
    if gu:
        parts.append(f"{', '.join(gu)}는 시군구 평균")
    if not parts:
        return " 이 수치는 시군구 평균값이며 대지 고유값이 아니다(참고용)."
    return " 기준: " + "; ".join(parts) + " (모두 대지 고유값이 아님·참고용)."


def _rule_based(region_name: str, year: int, use_type: str, facts: List[dict], imps: List[dict]) -> str:
    """규칙 기반 폴백 문단 — 순수 코드, 수치는 facts 그대로. 비교(높다/낮다)는 산술."""
    clauses = []
    for f in facts:
        unit = f.get("unit", "")
        na = f.get("national_avg")
        # 절대수(총인구·세대수 등, 단위 명·세대)를 전국 총량과 비교하면 늘 "낮다"가 되어 무의미 —
        # 비율(%) 지표만 전국 대비 (compute_index 와 동일 게이트, 절대 원칙 4)
        if na is None or unit != "%":
            clauses.append(f"{f['item']}은 {f['value']}{unit}")
        else:
            rel = "높다" if f["value"] > na else ("낮다" if f["value"] < na else "비슷하다")
            clauses.append(f"{f['item']}은 {f['value']}{unit}로 전국({na}{unit})보다 {rel}")
    body = ", ".join(clauses)
    imp_txt = ""
    if imps:
        imp_txt = " 참고할 검토 사항으로 " + "; ".join(i["text"] for i in imps) + " 등이 있다(참고)."
    return (
        f"{region_name} 기준 {year}년 {use_type} 용도 관점의 통계다. {body}.{imp_txt}"
        f"{_scope_disclaimer(facts)}"
    )


def compose_narrative(
    region_name: str,
    year: int,
    use_type: str,
    facts: List[dict],
    implications: List[dict],
) -> Tuple[str, str]:
    """(문단, source) 반환. source 는 'ai' 또는 'rule_based_fallback'."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _rule_based(region_name, year, use_type, facts, implications), "rule_based_fallback"

    try:
        import anthropic

        client = anthropic.Anthropic()
        user = (
            f"지역: {region_name}\n연도: {year}\n건물 용도: {use_type}\n\n"
            f"[facts]\n{_facts_block(facts)}\n\n[implications(참고)]\n{_imps_block(implications)}\n\n"
            f"위 facts 의 수치만 사용해 규칙대로 한 문단을 써라."
        )
        resp = client.with_options(timeout=_TIMEOUT_S).messages.create(
            model=_MODEL,
            max_tokens=800,
            output_config={"effort": "low"},
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        if resp.stop_reason == "refusal":
            return _rule_based(region_name, year, use_type, facts, implications), "rule_based_fallback"
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            return _rule_based(region_name, year, use_type, facts, implications), "rule_based_fallback"
        return text, "ai"
    except Exception:
        # 키 오류·타임아웃·네트워크·SDK 오류 등 무엇이든 → 규칙 폴백 (facts 보존)
        return _rule_based(region_name, year, use_type, facts, implications), "rule_based_fallback"
