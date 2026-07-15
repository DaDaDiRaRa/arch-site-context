"""컨셉·설계방향 제안 (발표 커버 슬라이드용) — S4 원칙의 *의도적·격리된* 예외.

무엇인가: 종합 읽기 PPT 마지막에 붙는 "PROJECT DIRECTION" 커버 한 장. 이미지처럼 컨셉명 +
키워드 3개로 설계 방향을 제안한다. 이건 **창작(네이밍·컨셉)** 이라 S4 ②의 "새 숫자 금지"를
넘어 "새 서사"까지 만든다 — 앱의 다른 곳에선 금지된 행위다.

왜 허용하나 (사용자 결정, 2026-07-16): 발표용 임팩트를 위해 이 한 기능에 한해 원칙 완화.
대신 **격리(quarantine)** 로 나머지 앱의 정직성을 지킨다:
  1) 벽 + 라벨은 유지 — 코드가 항상 CONCEPT_LABEL 부착 (AI 제안·검증 보장 없음). 모델에 안 맡김.
  2) 근거 인용 유지 — 컨셉명은 창작이되, 각 키워드는 어느 드라이버/사실에서 나왔는지 basis 로 추적.
  3) ★ 기계 계약에 절대 안 흘림 — 이 결과는 BoardResult/board_brief/project_seed/MCP 에 **안 들어간다**.
     그래서 스키마(pydantic) 도 만들지 않고 plain dict 로만 존재하며, board_pptx 경로에서만 계산해
     덱 조립용 dict 에 주입한다. competition 형제앱이 이 컨셉을 실측인 척 삼켜 이중 의견이 나는 것을 원천 차단.

모델은 Claude(원칙 6) — synthesis ② 와 동일한 Opus. 키 없음·오류·파싱 실패 시 규칙 폴백
(드라이버 이름을 키워드로, 창작 네이밍 없음 — 정직).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, List, Optional

from app.services import synthesis

_MODEL = "claude-opus-4-8"  # ② 와 동일 — 한국어 창작·추론

# 코드가 항상 부착하는 라벨 (모델 출력과 무관). 컨셉은 '사실'이 아니라 '제안'임을 못박음.
CONCEPT_LABEL = (
    "AI 제안입니다. 검증·재현이 보장되지 않으며, 컨셉·네이밍은 발표용 참고안입니다. "
    "정식 컨셉·제안서 작성과 최종 결정은 사람이 합니다."
)

_SYSTEM = (
    "당신은 건축 대지분석을 '설계 방향 제안'으로 번역하는 조력자다. 아래 '검증된 사실'과 "
    "'지배 설계 드라이버'를 근거로, 발표 커버 슬라이드에 쓸 컨셉 방향을 제안한다.\n"
    "이건 검증된 사실이 아니라 AI 제안이다. 그럼에도 다음을 반드시 지킨다:\n"
    "(a) 각 키워드는 반드시 위에 제시된 드라이버/사실 중 하나에서 나온다. 근거 없는 키워드 금지.\n"
    "(b) 새 숫자를 만들지 않는다. 사업성 금액·수익률·면적 등 제공되지 않은 수치 단정 금지.\n"
    "(c) 좋다/나쁘다 단정이 아니라 '이 대지가 요구하는 설계 방향'을 서술한다.\n"
    "출력은 **오직 JSON 객체 하나**로만 한다(설명·머리말·코드펜스 없이):\n"
    '{"name": "컨셉명(짧고 강한 한 단어, 영문 대문자 또는 한글)", '
    '"tagline": "한 줄 부제(선택, 없으면 빈 문자열)", '
    '"keywords": [{"word": "키워드(2~5자)", "gloss": "이 대지에서 이것이 뜻하는 설계 방향 한 줄", '
    '"basis": "근거가 된 드라이버명 또는 사실"}]}\n'
    "키워드는 3개(최대 4개). 용도({use_type}) 관점에서 이 대지의 지배적 방향을 담는다."
)


def _rule_concept(drivers: List[Any], archetype: Any) -> Optional[dict]:
    """규칙 폴백 — 드라이버 이름을 키워드로. 창작 네이밍은 안 만든다(정직).

    name 을 비워 두면 슬라이드가 컨셉명 대신 '설계 방향'을 헤드라인으로 쓴다.
    """
    kws: List[dict] = []
    for d in (drivers or [])[:3]:
        name = synthesis._g(d, "name") or ""
        if not name:
            continue
        ev = synthesis._g(d, "evidence") or []
        basis = " · ".join(f"{synthesis._g(e,'key')} {synthesis._g(e,'detail')}" for e in ev[:1])
        kws.append({
            "word": name,
            "gloss": synthesis._g(d, "response") or "",
            "basis": basis or f"{synthesis._g(d,'rank') or ''}순위 드라이버".strip(),
        })
    if not kws:
        return None
    return {
        "name": "",  # 창작명 없음 — 규칙 폴백은 드라이버 이름만
        "tagline": synthesis._g(archetype, "name") or "",
        "keywords": kws,
        "source": "rule_based_fallback",
        "model": "",
        "label": CONCEPT_LABEL,
    }


def _parse(text: Optional[str]) -> Optional[dict]:
    """모델 출력에서 JSON 객체 추출·검증. 실패 시 None (호출부가 규칙 폴백)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    kws_raw = obj.get("keywords")
    if not isinstance(kws_raw, list):
        return None
    kws: List[dict] = []
    for k in kws_raw[:4]:
        if not isinstance(k, dict) or not (k.get("word") or "").strip():
            continue
        kws.append({
            "word": str(k.get("word", "")).strip()[:10],
            "gloss": str(k.get("gloss", "")).strip()[:80],
            "basis": str(k.get("basis", "")).strip()[:80],
        })
    if not kws:
        return None
    return {
        "name": str(obj.get("name", "")).strip()[:24],
        "tagline": str(obj.get("tagline", "")).strip()[:80],
        "keywords": kws,
    }


def derive_concept(use_type, facts=None, diagnoses=None, hazards=None, cross=None,
                   drivers=None, archetype=None) -> Optional[dict]:
    """컨셉·설계방향 제안 dict 또는 None. 근거(드라이버/사실) 없으면 None (억지 창작 금지).

    반환은 plain dict — 스키마·계약 밖. board_pptx 경로에서만 호출해 덱 dict 에 주입한다.
    """
    facts = facts or []
    drivers = drivers or []
    # 드라이버(또는 최소한 facts)가 없으면 근거가 없어 컨셉을 만들지 않는다.
    if not drivers and not facts:
        return None
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _rule_concept(drivers, archetype)

    pool = synthesis._pool_text(facts, diagnoses, hazards, cross, drivers, archetype)
    user = (
        f"건물 용도: {use_type}\n\n[검증된 사실 · 지배 드라이버]\n{pool}\n\n"
        f"위 근거로 {use_type} 관점의 컨셉 방향을 규칙대로 JSON 으로만 제안하라."
    )
    text = synthesis._call(
        _MODEL, _SYSTEM.replace("{use_type}", use_type), user,
        thinking=True, effort="medium", max_tokens=2000, timeout=90.0,
    )
    parsed = _parse(text)
    if parsed is None:
        return _rule_concept(drivers, archetype)
    parsed["source"] = "ai"
    parsed["model"] = _MODEL
    parsed["label"] = CONCEPT_LABEL
    return parsed
