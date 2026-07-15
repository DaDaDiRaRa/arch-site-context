"""S4 — 종합 산출 두 블록 (CLAUDE.md §8.11). /board 통합 풀 위에서만 돈다.

**정직성 핵심 = 분리 + 라벨.** 위험은 "AI 의견이 사실인 척하는 것". 그래서 산출을 벽으로 나눈다:
  ① 사실 종합(해석) — 검증된 사실(facts·수급·재해·교차시사점)만 인용한 그라운디드 서술. '참고'.
  ② AI 판단(의견) — 그 위 AI 의견. **분리·라벨**("검증/재현 보장 없음·최종결정은 사람").

둘 다:
- 새 숫자 절대 안 만듦 — 풀에 있는 값만 인용 (절대 원칙 1·2).
- 그라운딩 사실이 없으면 no_data 로 멈춤 — 환각 금지 (절대 원칙 3).
- Claude 하나(원칙6, Claude 계열 유지). ①=Sonnet(서술·싸고 충분), ②=Opus(추론 정교, adaptive thinking).
- 키 없음·오류·타임아웃·refusal → 규칙 폴백. ②의 폴백은 가짜 의견을 만들지 않고 '판단 유보'.

⚠️ §2.5 완화 반영: "판단은 분리·라벨해 제시하되 *최종 결정*은 사람". ②는 근거 fact 인용 + 가정 명시 +
새 숫자 금지 3조건을 프롬프트로 강제하고, 라벨은 코드가 항상 부착한다(모델에 맡기지 않음).
"""

from __future__ import annotations

import os
from typing import Any, List, Optional, Tuple

from app.schemas.board import Synthesis

_INTERP_MODEL = "claude-sonnet-5"   # ① 서술 — 싸고 충분
_JUDGE_MODEL = "claude-opus-4-8"    # ② 판단 — 추론 정교

# ②의 벽 라벨 — 코드가 항상 부착 (모델 출력과 무관하게 보장). 사실(①)과 혼동 방지.
JUDGMENT_LABEL = (
    "아래는 AI 의견입니다. 검증·재현이 보장되지 않으며, 인용한 근거 외의 판단은 가정에 기반합니다. "
    "최종 판단·결정은 사람이 합니다."
)


# ─────────────────────────────────────────────────────────────────────────────
# 값 추출 (dict / pydantic 모델 공용)
# ─────────────────────────────────────────────────────────────────────────────

def _g(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ─────────────────────────────────────────────────────────────────────────────
# 그라운딩 컨텍스트 — 풀의 사실을 프롬프트용 텍스트로 (근접도·출처 포함)
# ─────────────────────────────────────────────────────────────────────────────

def _facts_block(facts: List[Any]) -> str:
    if not facts:
        return "(없음)"
    lines = []
    for f in facts:
        na = _g(f, "national_avg")
        unit = _g(f, "unit", "") or ""
        na_txt = f", 전국 {na}{unit}" if na is not None else ""
        prox = _g(f, "proximity") or _g(f, "scope_level") or ""
        scope = _g(f, "scope") or ""
        lines.append(
            f"- {_g(f,'item')}: {_g(f,'value')}{unit}{na_txt} "
            f"[기준 {scope}·근접도 {prox}·{_g(f,'source_tbl')} {_g(f,'year')}]"
        )
    return "\n".join(lines)


def _diag_block(diagnoses: List[Any]) -> str:
    if not diagnoses:
        return "(없음)"
    lines = []
    for d in diagnoses:
        dem = _g(d, "demand")
        sup = _g(d, "supply")
        lines.append(
            f"- {_g(d,'name')}: 수요 {_g(dem,'level')}·공급 {_g(sup,'level')} "
            f"({_g(sup,'kinds')} {_g(sup,'count')}개, 반경 {_g(sup,'radius')}m) [참고]"
        )
    return "\n".join(lines)


def _hazard_block(hazards: Any) -> str:
    if hazards is None:
        return "(확인 불가)"
    lines = []
    for label, key in (("홍수", "flood"), ("산사태", "landslide")):
        zone = _g(hazards, key)
        iz = _g(zone, "in_zone")
        if iz is True:
            exps = _g(zone, "exposures") or []
            exp_txt = ", ".join(f"{_g(e,'metric')} {_g(e,'affected')}{_g(e,'unit','') or ''}" for e in exps)
            lines.append(f"- {label} 위험 영향범위 포함" + (f" (영향: {exp_txt})" if exp_txt else ""))
        elif iz is False:
            lines.append(f"- {label} 위험 영향범위 외")
    hw = _g(hazards, "heatwave")
    if hw is not None:
        lines.append(
            f"- 최근 여름 폭염특보: 경보 {_g(hw,'alert_count',0)}건·주의보 {_g(hw,'warning_count',0)}건"
            f" ({_g(hw,'scope','') or ''})"
        )
    return "\n".join(lines) if lines else "(위험지도 확인 불가)"


def _cross_block(cross: List[Any]) -> str:
    if not cross:
        return "(없음)"
    lines = []
    for c in cross:
        basis = _g(c, "basis") or []
        b_txt = "; ".join(f"{_g(b,'key')}={_g(b,'detail')}" for b in basis)
        lines.append(f"- [{'·'.join(_g(c,'domains') or [])}] {_g(c,'text')} (근거: {b_txt})")
    return "\n".join(lines)


def _drivers_block(drivers) -> str:
    if not drivers:
        return "(없음)"
    lines = []
    for d in drivers:
        ev = _g(d, "evidence") or []
        ev_txt = "; ".join(f"{_g(e,'key')}={_g(e,'detail')}" for e in ev)
        lines.append(f"- {_g(d,'rank')}순위 {_g(d,'name')}: {_g(d,'response')} (근거: {ev_txt})")
    return "\n".join(lines)


def _archetype_line(archetype) -> str:
    if not archetype:
        return "(미분류)"
    alts = _g(archetype, "alternatives") or []
    alt_txt = f" (차점: {', '.join(alts)})" if alts else ""
    return f"{_g(archetype,'name')} [{_g(archetype,'group')}] — {_g(archetype,'description')}{alt_txt}"


def _pool_text(facts, diagnoses, hazards, cross, drivers=None, archetype=None) -> str:
    return (
        f"[동네 유형 (T1.5·참고)]\n{_archetype_line(archetype)}\n\n"
        f"[인구·통계 facts]\n{_facts_block(facts)}\n\n"
        f"[수급진단 (참고)]\n{_diag_block(diagnoses)}\n\n"
        f"[재해위험 사실]\n{_hazard_block(hazards)}\n\n"
        f"[교차 시사점 (S2·참고)]\n{_cross_block(cross)}\n\n"
        f"[지배 설계 드라이버 (T2·검토 신호)]\n{_drivers_block(drivers)}"
    )


def _has_grounding(facts, diagnoses, hazards, cross) -> bool:
    if facts or diagnoses or cross:
        return True
    if hazards is not None:
        for key in ("flood", "landslide"):
            if _g(_g(hazards, key), "in_zone") is not None:
                return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 프롬프트
# ─────────────────────────────────────────────────────────────────────────────

_INTERP_SYSTEM = (
    "당신은 건축 대지분석 보조자다. 아래 '검증된 사실'만 사용해 \"이 필지는 어떤 곳인가\"를 "
    "한국어 **3문장 이내로 핵심만 간결하게** 서술한다(발표 슬라이드용 — 짧고 밀도 높게).\n"
    "규칙(반드시 지킴):\n"
    "1) 제공된 사실의 수치·항목만 인용한다. 제공되지 않은 숫자·시설·항목을 절대 만들지 않는다.\n"
    "2) 좋다/나쁘다·사업성·전망·수익 같은 단정을 쓰지 않는다. 사실 서술만. 교차 시사점·수급진단은 "
    "'참고 검토사항'으로만 부드럽게 언급하고 단정하지 않는다.\n"
    "3) 각 수치의 기준 지역과 근접도(대지>반경>읍면동>시군구>proxy)를 밝힌다. 시군구 평균은 대지 "
    "고유값이 아님을 명시한다. 기준이 섞여 있으면 어느 지표가 어느 기준인지 구분해 쓴다.\n"
    "4) 건물 용도 관점에서 관련 사실을 자연스럽게 묶어 이 필지의 특징을 서술한다.\n"
    "5) 문단 텍스트만 출력한다(제목·목록·머리말 없이)."
)

_JUDGE_SYSTEM = (
    "당신은 건축 설계 관점의 조언자다. 아래 '검증된 사실' 위에서 건물 용도 관점의 '의견'을 제시한다. "
    "이것은 검증된 사실이 아니라 AI 의견임을 전제로 한다.\n"
    "반드시 지킬 3조건:\n"
    "(a) 모든 의견에 근거가 된 사실(어떤 수치·진단·재해)을 함께 인용한다.\n"
    "(b) 추정에는 가정을 명시한다('~라고 가정하면').\n"
    "(c) 새 숫자를 절대 만들지 않는다. 사업성 금액·수익률·구체 면적 등 제공되지 않은 수치 단정 금지.\n"
    "형식·태도:\n"
    "- 용도({use_type}) 관점에서 적합/유의 신호를 서술형으로 제시한다(점수·순위·금액 아님).\n"
    "- '반드시 ~하라'는 지시가 아니라 '검토할 신호' 수준으로 쓴다. 최종 결정은 사람 몫임을 존중한다.\n"
    "- 사실이 부족한 부분은 정직하게 '확인 필요'라고 쓴다. 없는 근거로 의견을 지어내지 않는다.\n"
    "- **3문장 이내로 핵심만 간결하게**(발표 슬라이드용), 문단 텍스트만 출력한다."
)


# ─────────────────────────────────────────────────────────────────────────────
# 규칙 폴백 (키 없음·오류)
# ─────────────────────────────────────────────────────────────────────────────

def _rule_interpretation(use_type, facts, diagnoses, hazards, cross) -> str:
    """규칙 기반 ① 서술 — 순수 코드, 수치는 풀 그대로 (새 숫자 없음)."""
    parts: List[str] = []
    if facts:
        clauses = []
        for f in facts[:6]:
            unit = _g(f, "unit", "") or ""
            na = _g(f, "national_avg")
            if na is None:
                clauses.append(f"{_g(f,'item')} {_g(f,'value')}{unit}")
            else:
                v = _g(f, "value")
                rel = "높음" if v > na else ("낮음" if v < na else "비슷")
                clauses.append(f"{_g(f,'item')} {v}{unit}(전국 {na}{unit} 대비 {rel})")
        parts.append(f"{use_type} 용도 관점 통계: " + ", ".join(clauses) + ".")
    low = [d for d in diagnoses if _g(_g(d, "supply"), "level") == "적음"]
    if low:
        parts.append("공급이 상대적으로 적은 항목: " + ", ".join(_g(d, "name") for d in low) + " (참고).")
    hz = _hazard_block(hazards)
    if hz not in ("(확인 불가)", "(위험지도 확인 불가)"):
        parts.append("재해: " + hz.replace("\n- ", " / ").replace("- ", ""))
    if cross:
        parts.append("교차 참고 시사점 " + str(len(cross)) + "건.")
    parts.append("모든 수치는 표기된 기준·근접도 기준이며 대지 고유값이 아닐 수 있다(참고).")
    text = " ".join(parts)
    # 그라운딩 풀 길이 상한 (비용·컨텍스트 폭주 방지). facts 는 KOSIS/규칙 출처라
    # 정상 규모면 넉넉히 들어가고, 이상 증식 시에만 절삭 + 표시.
    _CAP = 8000
    if len(text) > _CAP:
        text = text[:_CAP] + " …(이하 생략·풀 상한)"
    return text


def _rule_judgment() -> str:
    """규칙 기반 ② — 가짜 의견을 만들지 않고 '판단 유보' (정직성)."""
    return (
        "AI 판단(의견)을 생성할 수 없습니다(모델 키 미설정 또는 오류). 위 검증된 사실과 교차 시사점을 "
        "근거로 사람이 직접 판단하시기 바랍니다. 데이터 밖의 의견을 임의로 생성하지 않습니다."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Claude 호출 (narrative.py 패턴)
# ─────────────────────────────────────────────────────────────────────────────

def _call(model: str, system: str, user: str, *, thinking: bool, effort: str,
          max_tokens: int, timeout: float) -> Optional[str]:
    """Claude 1회. 성공 시 텍스트, refusal/빈응답/오류면 None (호출부가 폴백)."""
    try:
        import anthropic

        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            output_config={"effort": effort},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}
        resp = anthropic.Anthropic().with_options(timeout=timeout).messages.create(**kwargs)
        if getattr(resp, "stop_reason", None) == "refusal":
            return None
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return text or None
    except Exception:  # noqa: BLE001 — 키·타임아웃·네트워크·SDK 무엇이든 폴백
        return None


def compose_interpretation(use_type, facts, diagnoses, hazards, cross, drivers=None, archetype=None) -> Tuple[str, str, str]:
    """① 사실 종합(해석). (text, source, model)."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _rule_interpretation(use_type, facts, diagnoses, hazards, cross), "rule_based_fallback", ""
    user = (
        f"건물 용도: {use_type}\n\n[검증된 사실]\n{_pool_text(facts, diagnoses, hazards, cross, drivers, archetype)}\n\n"
        f"위 사실의 수치만 사용해 규칙대로 이 필지를 3문장 이내로 간결히 서술하라."
    )
    text = _call(_INTERP_MODEL, _INTERP_SYSTEM, user,
                 thinking=False, effort="low", max_tokens=1500, timeout=45.0)
    if text is None:
        return _rule_interpretation(use_type, facts, diagnoses, hazards, cross), "rule_based_fallback", ""
    return text, "ai", _INTERP_MODEL


def compose_judgment(use_type, facts, diagnoses, hazards, cross, drivers=None, archetype=None) -> Tuple[str, str, str]:
    """② AI 판단(의견). (text, source, model). 폴백은 '판단 유보'(가짜 의견 금지)."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _rule_judgment(), "rule_based_fallback", ""
    user = (
        f"건물 용도: {use_type}\n\n[검증된 사실]\n{_pool_text(facts, diagnoses, hazards, cross, drivers, archetype)}\n\n"
        f"위 사실 위에서 {use_type} 용도 관점의 의견을 3조건(근거 인용·가정 명시·새 숫자 금지)을 지켜 쓰라."
    )
    system = _JUDGE_SYSTEM.replace("{use_type}", use_type)
    text = _call(_JUDGE_MODEL, system, user,
                 thinking=True, effort="medium", max_tokens=6000, timeout=90.0)
    if text is None:
        return _rule_judgment(), "rule_based_fallback", ""
    return text, "ai", _JUDGE_MODEL


def synthesize(use_type, facts=None, diagnoses=None, hazards=None, cross=None, drivers=None, archetype=None) -> Synthesis:
    """/board 통합 풀 → 두 블록. 그라운딩 사실 없으면 no_data(환각 금지)."""
    facts = facts or []
    diagnoses = diagnoses or []
    cross = cross or []
    drivers = drivers or []

    if not _has_grounding(facts, diagnoses, hazards, cross):
        msg = "그라운딩할 검증된 사실이 없어 종합 해석/판단을 생성하지 않습니다(확인 불가)."
        return Synthesis(
            interpretation=msg, interpretation_source="no_data",
            judgment=msg, judgment_source="no_data", judgment_label=JUDGMENT_LABEL,
        )

    itext, isrc, imodel = compose_interpretation(use_type, facts, diagnoses, hazards, cross, drivers, archetype)
    jtext, jsrc, jmodel = compose_judgment(use_type, facts, diagnoses, hazards, cross, drivers, archetype)
    return Synthesis(
        interpretation=itext, interpretation_source=isrc, interpretation_model=imodel,
        judgment=jtext, judgment_source=jsrc, judgment_model=jmodel,
        judgment_label=JUDGMENT_LABEL,
    )
