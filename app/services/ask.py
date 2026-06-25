"""P10 물어보기 — 우리 데이터(A·B·P11) 위에서만 답하는 Q&A (Claude 1회).

기본: 번들 안 수치만 인용해 답하고, 답 못하면 '확인 불가'로 멈춘다 (절대 원칙 1·3, 환각 금지).
모델은 Claude 하나 (원칙 6). 데이터 밖은 사용자가 web=True 로 명시할 때만 내장 web_search 폴백
— 결과는 '외부·참고' + 출처로 분리. 키 없으면 정직하게 미설정 안내(추정 0).
"""

from __future__ import annotations

import os
from datetime import date
from typing import List, Tuple

import httpx

from app.schemas.ask import AskRequest, AskResult, WebSource
from app.schemas.region import Fact
from app.services import compare
from app.services.narrative import _facts_block

_MODEL = "claude-opus-4-8"
_TIMEOUT_S = 40.0
_NO_DATA_PREFIX = "확인 불가"

_SYSTEM_GROUNDED = (
    "당신은 건축 대지분석 보조자다. 아래 [데이터]에 있는 수치만 사용해 사용자의 질문에 한국어로 답한다.\n"
    "규칙(반드시 지킴):\n"
    "1) [데이터]의 facts·시설개수·수급진단에 있는 값만 인용한다. 제공되지 않은 숫자·항목·시설을 만들지 않는다.\n"
    "2) 기억·추정·일반지식으로 답하지 않는다. [데이터]로 답할 수 없으면, 다른 말 없이 정확히 "
    f"'{_NO_DATA_PREFIX}: ' 로 시작해 무엇이 없어 답할 수 없는지 한 문장으로 밝힌다.\n"
    "3) 좋다/나쁘다·사업성·전망·권고 같은 단정을 쓰지 않는다. 수치를 근거로 사실만 서술하고, "
    "수급진단 등 해석성 항목은 '참고'로만 부드럽게 언급한다 (판단은 사람).\n"
    "4) 통계는 시군구 평균값이며 대지 고유값이 아님을 필요 시 밝힌다. 2~4문장으로 간결히.\n"
    "5) 인용한 수치에는 가능하면 출처표(source_tbl)나 '전국 대비'를 함께 언급한다."
)

_SYSTEM_WEB = (
    "당신은 건축 대지분석 보조자다. 사용자의 질문에 웹검색 결과로 답한다.\n"
    "규칙: 1) web_search 로 찾은 내용만 쓰고 출처를 밝힌다. 2) 추정·단정 말고 사실·'참고'로만 제시한다.\n"
    "3) 좋다/나쁘다 판단은 하지 않는다 (판단은 사람). 2~4문장 한국어로 간결히."
)


def _bundle_context(facts: List[dict], counts: dict, diagnoses: list) -> str:
    """번들을 프롬프트용 텍스트로. 모든 인용 가능한 수치를 명시(출처 포함)."""
    parts = ["[지역 통계 facts]", _facts_block(facts) or "(없음)"]
    parts.append("\n[반경 내 시설 개수]")
    parts.append("\n".join(f"- {k}: {v}개" for k, v in counts.items()) or "(없음)")
    parts.append("\n[수급진단(참고)]")
    if diagnoses:
        for d in diagnoses:
            parts.append(f"- {d.name}: {d.signal} — {d.note}")
    else:
        parts.append("(없음)")
    return "\n".join(parts)


def answer_grounded(bundle: dict, question: str) -> Tuple[str, bool, str, List[str]]:
    """(answer, answerable, source, notes). 키 없으면 ai_unavailable(환각 안 함)."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return (
            "물어보기(AI)가 설정되지 않았습니다. ANTHROPIC_API_KEY 가 필요합니다.",
            False,
            "ai_unavailable",
            [],
        )
    try:
        import anthropic

        client = anthropic.Anthropic()
        region = bundle.get("region")
        rname = region.name if region else "해당 지역"
        ctx = _bundle_context(bundle["facts"], bundle["counts"], bundle["diagnoses"])
        user = (
            f"지역: {rname} (시군구 평균)\n\n[데이터]\n{ctx}\n\n"
            f"질문: {question}\n\n위 [데이터]의 수치만 사용해 규칙대로 답하라."
        )
        resp = client.with_options(timeout=_TIMEOUT_S).messages.create(
            model=_MODEL,
            max_tokens=1024,
            output_config={"effort": "medium"},
            system=_SYSTEM_GROUNDED,
            messages=[{"role": "user", "content": user}],
        )
        if resp.stop_reason == "refusal":
            return (f"{_NO_DATA_PREFIX}: 요청을 처리할 수 없습니다.", False, "no_data", [])
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            return (f"{_NO_DATA_PREFIX}: 답변을 생성하지 못했습니다.", False, "no_data", [])
        answerable = not text.startswith(_NO_DATA_PREFIX)
        return text, answerable, ("ai" if answerable else "no_data"), []
    except Exception as e:
        # 키오류·타임아웃 등 — 추정하지 않고 정직하게 멈춤 (환각 금지)
        return (f"{_NO_DATA_PREFIX}: AI 응답 실패({type(e).__name__}).", False, "no_data", [])


def _collect_sources(content) -> List[WebSource]:
    """응답 content 에서 웹 출처(url·title) 방어적 추출 (SDK 블록 구조 변화 대비)."""
    out: List[WebSource] = []
    seen = set()

    def add(url, title):
        if url and url not in seen:
            seen.add(url)
            out.append(WebSource(title=title or "", url=url))

    for block in content or []:
        btype = getattr(block, "type", "")
        if btype == "web_search_tool_result":
            for r in getattr(block, "content", []) or []:
                add(getattr(r, "url", None), getattr(r, "title", None))
        if btype == "text":
            for c in getattr(block, "citations", None) or []:
                add(getattr(c, "url", None), getattr(c, "title", None))
    return out


def answer_web(question: str, region_name: str) -> Tuple[str, List[WebSource], str, List[str]]:
    """(answer, web_sources, source, notes). 미지원/실패 시 '미연결' 정직 표시(환각 안 함)."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return ("웹검색(AI)이 설정되지 않았습니다.", [], "ai_unavailable", [])
    try:
        import anthropic

        client = anthropic.Anthropic()
        tools = [{"type": "web_search_20260209", "name": "web_search"}]
        messages = [{"role": "user", "content": f"({region_name} 관련) {question}"}]
        resp = client.with_options(timeout=90.0).messages.create(
            model=_MODEL, max_tokens=2048, system=_SYSTEM_WEB,
            tools=tools, messages=messages,
        )
        # 서버툴 루프가 길면 pause_turn — 몇 번 이어받기
        for _ in range(4):
            if resp.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": resp.content})
            resp = client.with_options(timeout=90.0).messages.create(
                model=_MODEL, max_tokens=2048, system=_SYSTEM_WEB,
                tools=tools, messages=messages,
            )
        if resp.stop_reason == "refusal":
            return ("웹검색 요청이 거부되었습니다.", [], "ai_web", ["웹검색 거부"])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        sources = _collect_sources(resp.content)
        if not text:
            return ("웹검색 결과를 가져오지 못했습니다.", sources, "ai_web", ["웹검색 결과 없음"])
        return text, sources, "ai_web", []
    except Exception as e:
        # web_search 미지원/네트워크 등 — 환각 대신 정직하게 미연결 표시 (degrade)
        return ("웹검색을 사용할 수 없습니다(미연결).", [], "ai_web", [f"웹검색 미연결: {type(e).__name__}"])


def build_answer(req: AskRequest) -> AskResult:
    """번들(A·B·P11) 구성 후 그라운디드 답변(기본) 또는 웹폴백(opt-in)."""
    client = httpx.Client(timeout=15.0)
    try:
        bundle = compare.gather_bundle(
            req.address, req.use_type, req.radius, req.kinds, client
        )
    finally:
        client.close()

    region = bundle["region"]
    base = dict(
        question=req.question,
        region=region,
        facts=[Fact(**f) for f in bundle["facts"]],
        counts=bundle["counts"],
        diagnoses=bundle["diagnoses"],
        base_date=date.today().isoformat(),
        notes=list(bundle["notes"]),
    )

    if req.web:
        answer, sources, source, wnotes = answer_web(req.question, region.name)
        return AskResult(
            answer=answer, answerable=(source == "ai_web" and not wnotes),
            source=source, web_sources=sources, **{**base, "notes": base["notes"] + wnotes}
        )

    answer, answerable, source, anotes = answer_grounded(bundle, req.question)
    return AskResult(
        answer=answer, answerable=answerable, source=source,
        **{**base, "notes": base["notes"] + anotes},
    )
