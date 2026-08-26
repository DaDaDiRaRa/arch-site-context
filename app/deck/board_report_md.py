"""종합 대지 읽기 HWP 보고서 — BoardResult dict → 마크다운 (§8.15 HWP 내보내기).

`board_slides.py`(PPTX)와 같은 입력(dict, `full.model_dump()` — `POST /board/hwp` 라우터가
`board()` 를 그대로 재사용)을 받아 같은 내용(아키타입·①②종합·설계드라이버·교차시사점·POR·
방법론)을 문서형으로 낸다. 새 숫자 0 — 값은 board 그대로, PPTX 와 마찬가지로 재계산 안 함
(절대 원칙 1·2). 심의·조합 제출은 HWP 가 사실상 표준이라(CLAUDE.md §8.15) PPTX 옆에 나란히
두는 옵션 — 여기서 만든 마크다운을 `services/kordoc_client.markdown_to_hwpx` 가 HWPX 로 바꾼다.

컨셉(§8.14, board['concept'])은 §2.5 원칙(판단은 분리·라벨)의 의도적 예외라 board_pptx
라우터가 렌더 직전에만 주입한다 — 여기서도 **호출자가 board dict 에 이미 넣어줬을 때만**
렌더하고, BoardResult 계약 자체엔 이 키가 없다(격리 유지).
"""

from __future__ import annotations

from typing import Any, Dict, List


def _txt(v: Any, n: int = 400) -> str:
    s = v.strip() if isinstance(v, str) else str(v or "")
    return s[:n]


def _n(v: Any) -> str:
    try:
        f = float(v)
        return f"{int(f):,}" if f == int(f) else f"{f:,.1f}"
    except (TypeError, ValueError):
        return str(v or "-")


def _md_table(headers: List[str], rows: List[List[Any]]) -> str:
    """GFM 표 — kordoc markdownToHwpx 가 그대로 HWPX 표로 변환."""
    if not rows:
        return ""
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        cells = [str(c).replace("|", "\\|").replace("\n", " ") for c in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _section_cover(board: Dict) -> List[str]:
    site = board.get("site") or {}
    arch = board.get("archetype") or {}
    lines = ["# 종합 대지 읽기", "", f"**대지**: {site.get('address', '')}", ""]
    meta = [
        f"기준일 {board.get('base_date', '')}" if board.get("base_date") else "",
        f"용도 {board.get('use_type', '')}" if board.get("use_type") else "",
        f"분석단위 {board.get('resolution', '')}" if board.get("resolution") else "",
        f"반경 {board.get('radius')}m" if board.get("radius") else "",
    ]
    meta_line = " · ".join(m for m in meta if m)
    if meta_line:
        lines.append(meta_line)
        lines.append("")
    if arch.get("name"):
        lines.append(f"이 동네는 — **{arch['name']}** ({arch.get('group', '')})")
        lines.append("")
        if arch.get("description"):
            lines.append(_txt(arch["description"], 300))
        lines.append("")
    return lines


def _section_coverage(board: Dict) -> List[str]:
    cov = board.get("coverage") or []
    if not cov:
        return []
    rows = [[c.get("domain", ""), "확보" if c.get("available") else "확인 불가", _txt(c.get("detail"), 80)]
            for c in cov]
    return ["## 커버리지", "", _md_table(["도메인", "확보 여부", "내용"], rows), ""]


def _section_archetype(board: Dict) -> List[str]:
    arch = board.get("archetype") or {}
    if not arch:
        return []
    lines = ["## 동네 유형 (아키타입 · 참고)", "", f"**{arch.get('name', '')}** — {arch.get('group', '')}", ""]
    if arch.get("description"):
        lines.append(_txt(arch["description"], 400))
        lines.append("")
    ev = arch.get("evidence") or []
    if ev:
        lines.append("근거:")
        for e in ev[:6]:
            prox = f" ({e.get('proximity')})" if e.get("proximity") else ""
            lines.append(f"- {e.get('key')} — {e.get('detail')}{prox}")
        lines.append("")
    alts = arch.get("alternatives") or []
    if alts:
        lines.append(f"혼재 특성(차점): {', '.join(alts[:3])}")
        lines.append("")
    return lines


def _section_synthesis(board: Dict) -> List[str]:
    syn = board.get("synthesis") or {}
    itp, jdg = syn.get("interpretation"), syn.get("judgment")
    if not itp and not jdg:
        return []
    lines = ["## 종합 해석 · 의견", ""]
    if itp:
        lines += ["### ① 검증된 사실 (해석)", "", _txt(itp, 2000), ""]
    if jdg:
        label = syn.get("judgment_label") or ""
        heading = f"### ② AI 판단 (의견) — {label}" if label else "### ② AI 판단 (의견)"
        lines += [heading, "", _txt(jdg, 2000), ""]
    return lines


def _section_drivers(board: Dict) -> List[str]:
    drivers = board.get("design_drivers") or []
    if not drivers:
        return []
    lines = ["## 설계 드라이버 (참고 — 검토 신호, 최종 판단은 사람)", ""]
    for d in drivers[:5]:
        lines.append(f"{d.get('rank')}. **{d.get('name', '')}** (증거강도 {_n(d.get('strength'))})")
        if d.get("response"):
            lines.append(f"   - 응답: {_txt(d['response'], 200)}")
        ev = d.get("evidence") or []
        if ev:
            ev_txt = " · ".join(f"{e.get('key')} {e.get('detail')}" for e in ev[:3])
            lines.append(f"   - 근거: {ev_txt}")
    lines.append("")
    return lines


def _section_cross(board: Dict) -> List[str]:
    cross = board.get("cross_implications") or []
    if not cross:
        return []
    lines = ["## 교차시사점 (참고 — 규칙 조합·LLM 0, 판단 아님)", ""]
    for c in cross[:8]:
        domains = " × ".join(c.get("domains") or [])
        tag = f" [{domains}]" if domains else ""
        lines.append(f"- **{c.get('name', '')}**{tag} — {_txt(c.get('text'), 200)}")
        basis = c.get("basis") or []
        if basis:
            b_txt = " · ".join(f"{b.get('key')} {b.get('detail')}" for b in basis[:3])
            lines.append(f"  - 근거: {b_txt}")
    lines.append("")
    return lines


def _section_program(board: Dict) -> List[str]:
    por = board.get("program_implications") or []
    if not por:
        return []
    groups: Dict[str, list] = {}
    for p in por:
        groups.setdefault(p.get("category", "기타"), []).append(p)
    lines = ["## 프로그램 함의 (POR — 검토 체크리스트, 참고)", ""]
    for cat, items in groups.items():
        lines.append(f"### {cat}")
        for p in items:
            basis = ", ".join(p.get("basis") or [])
            suffix = f" (근거: {basis})" if basis else ""
            lines.append(f"- {_txt(p.get('recommendation'), 200)}{suffix}")
        lines.append("")
    return lines


def _section_concept(board: Dict) -> List[str]:
    """★ §8.14 격리 예외 — board dict 에 'concept' 이 이미 주입돼 있을 때만 렌더."""
    con = board.get("concept") or {}
    kws = con.get("keywords") or []
    if not kws:
        return []
    name = (con.get("name") or "").strip()
    tagline = f" — {con['tagline']}" if con.get("tagline") else ""
    lines = ["## AI 제안 · 설계 방향 (PROJECT DIRECTION)", "", f"**{name or '설계 방향'}**{tagline}", ""]
    for w in kws:
        word = str(w.get("word", "")).strip()
        gloss = _txt(w.get("gloss"), 100)
        basis = f" (근거: {_txt(w.get('basis'), 100)})" if w.get("basis") else ""
        lines.append(f"- **{word}**: {gloss}{basis}")
    lines.append("")
    if con.get("label"):
        lines.append(f"*{con['label']}*")
        lines.append("")
    return lines


def _section_indicators(board: Dict) -> List[str]:
    facts = [f for f in (board.get("facts") or []) if f.get("value") is not None]
    if not facts:
        return []
    rows = []
    for f in facts[:20]:
        idx = f.get("index")
        rows.append([
            f.get("item", ""),
            f"{_n(f.get('value'))}{f.get('unit', '')}",
            f"{_n(f.get('national_avg'))}{f.get('unit', '')}" if f.get("national_avg") is not None else "-",
            f"{_n(idx)} ({f.get('index_band')})" if idx is not None else "-",
            f.get("scope", "") or "-",
            f.get("source_tbl", ""),
        ])
    return ["## 인구·지역 지표 (전국=100 지수)", "",
            _md_table(["항목", "값", "전국평균", "지수", "기준지역", "출처"], rows), ""]


def _section_diagnoses(board: Dict) -> List[str]:
    diags = board.get("diagnoses") or []
    if not diags:
        return []
    rows = []
    for d in diags[:10]:
        demand, supply = d.get("demand") or {}, d.get("supply") or {}
        rows.append([
            d.get("name", ""),
            f"{demand.get('item', '')} {_n(demand.get('value'))}{demand.get('unit', '')} ({demand.get('level', '')})",
            f"{supply.get('count', '-')}개 ({supply.get('level', '')})",
            d.get("signal", ""),
        ])
    return ["## 수급 진단 (참고 — 휴리스틱, 최종 판단은 사람)", "",
            _md_table(["항목", "수요", "공급", "신호"], rows), ""]


def _zone_state(zone: Dict) -> str:
    """in_zone 3상태 — True/False/None(조회 실패). None 을 '밖'으로 단정하지 않는다 (절대 원칙 3)."""
    iz = zone.get("in_zone")
    if iz is True:
        return "영향범위 포함"
    if iz is False:
        return "영향범위 밖"
    return "확인 불가"


def _section_hazards(board: Dict) -> List[str]:
    hz = board.get("hazards") or {}
    if not hz:
        return []
    flood, landslide, heat = hz.get("flood") or {}, hz.get("landslide") or {}, hz.get("heatwave") or {}
    lines = ["## 재해위험 (참고 — 영향범위 포함 여부, SGIS)", ""]
    lines.append(f"- 홍수: {_zone_state(flood)}")
    lines.append(f"- 산사태: {_zone_state(landslide)}")
    if heat:
        lines.append(
            f"- 폭염특보: 경보 {heat.get('alert_count', 0)}건 · 주의보 {heat.get('warning_count', 0)}건"
            f" ({heat.get('base_period', '')})"
        )
    lines.append("")
    return lines


def _section_methodology(board: Dict) -> List[str]:
    meth = board.get("methodology") or {}
    sources = meth.get("sources") or []
    if not sources:
        return []
    lines = ["## 방법론 · 데이터 부록 (공모·감사 대비)", ""]
    if meth.get("summary"):
        lines.append(_txt(meth["summary"], 300))
        lines.append("")
    rows = [[s.get("name", ""), s.get("key", ""), s.get("publisher", ""), _txt(s.get("note"), 60)]
            for s in sources[:20]]
    lines.append(_md_table(["출처", "식별자", "발간기관", "비고"], rows))
    lines.append("")
    limits = meth.get("limitations") or []
    if limits:
        lines.append("### 한계")
        for lim in limits[:10]:
            lines.append(f"- {_txt(lim, 200)}")
        lines.append("")
    return lines


def build_board_report_md(board: Dict) -> str:
    """BoardResult dict → 종합 대지 읽기 HWP 보고서 마크다운. 데이터 없는 섹션은 graceful skip."""
    lines: List[str] = []
    lines += _section_cover(board)
    lines += _section_coverage(board)
    lines += _section_archetype(board)
    lines += _section_synthesis(board)
    lines += _section_drivers(board)
    lines += _section_cross(board)
    lines += _section_program(board)
    lines += _section_concept(board)  # opt-in — board['concept'] 있을 때만 (격리, §8.14)
    lines += _section_indicators(board)
    lines += _section_diagnoses(board)
    lines += _section_hazards(board)
    lines += _section_methodology(board)
    lines.append("---")
    lines.append(
        "본 문서는 터읽기(arch-site-context)가 자동 생성했습니다. "
        "①은 검증된 사실이며, ②·AI 제안은 검증/재현이 보장되지 않는 참고 의견으로 최종 결정은 사람이 합니다."
    )
    return "\n".join(lines).strip() + "\n"
