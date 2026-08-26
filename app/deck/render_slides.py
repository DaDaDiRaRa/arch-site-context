"""일반 슬라이드 렌더러 — **남이 준 내용을 우리 스타일로 그린다.**

## 왜 이게 있나

`map_slides.py`·`data_slides.py` 는 **우리가 모은 데이터**를 그린다. 이 모듈은 다르다 —
내용을 **밖에서 받아** 같은 A3 다크 프레임에 얹는다.

첫 사용처는 concept-studio(컨셉 스튜디오, `:8200`)의 컨셉 장표다. 그 앱이
「무엇을 적을 것인가」를 알고, 우리가 「어떻게 그릴 것인가」를 안다.
2026-08-25 에 deck-builder 를 흡수하면서 `style.py` 에 A3 네이티브 편집가능
조각(`kpi_card`·`table`·`caption_band`)이 모였고, 그걸 다시 만들 이유가 없다.

## 우리는 「컨셉」이 무엇인지 모른다

받는 낱말은 다섯뿐이다 — `cover`·`kpi`·`cards`·`table`·`text`.
전부 이미 우리 어휘다. 여기에 컨셉 전용 분기를 넣기 시작하면 이 앱이
남의 도메인을 알게 되고, 그러면 deck-builder 가 접힌 이유를 되풀이한다.

## 근거는 캡션으로 따라간다

PPTX 에는 `data-ev` 를 못 단다. 보내는 쪽이 `sources` 에 근거 번호를 모아 주면
캡션 밴드에 찍는다 — 심의 자리에서 「그 숫자 어디서 났습니까」에 장표만 보고 답하라고.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Cm, Pt

from app.deck import style as k

#: 한 장에 넣을 수 있는 최대치. 넘으면 **자르고 잘랐다고 캡션에 적는다** —
#: 조용히 없애면 발표자가 회의장에서 없는 줄 알고 넘어간다.
MAX_KPI = 4
MAX_CARDS = 4
MAX_ROWS = 12


def build(payload: Dict[str, Any]) -> bytes:
    """`deck_render/1.0` → A3 편집가능 PPTX bytes."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = k.A3_W, k.A3_H

    slides = payload.get("slides") or []
    if not slides:
        raise ValueError("그릴 슬라이드가 하나도 없다")

    for spec in slides:
        kind = str(spec.get("kind") or "text")
        drawer = _DRAWERS.get(kind)
        if drawer is None:
            #: 모르는 낱말은 **글로라도 남긴다.** 빈 장을 내면 왜 비었는지 아무도 모른다.
            drawer = _text
        drawer(prs, spec)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ── 장 하나씩 ───────────────────────────────────────────────────────────────


def _cover(prs, s: Dict[str, Any]) -> None:
    sl = k.blank_slide(prs)
    k.rect(sl, MSO_SHAPE.RECTANGLE, 0, Cm(11.3), k.A3_W, Cm(0.16), fill=k.RED)
    k.tb(sl, Cm(1.5), Cm(3.2), Cm(39), Cm(2.4), _s(s, "title"),
         size=44, color=k.WHITE, bold=True)
    if _s(s, "subtitle"):
        k.tb(sl, Cm(1.5), Cm(6.4), Cm(39), Cm(1), _s(s, "subtitle"), size=16, color=k.MUTE)
    if _s(s, "lead"):
        k.tb(sl, Cm(1.5), Cm(8.4), Cm(39), Cm(2.4), _s(s, "lead"), size=17, color=k.WHITE)
    body = _list(s, "body")
    if body:
        k.tb(sl, Cm(1.5), Cm(13), Cm(39), Cm(1.4), body, size=13, color=k.MUTE)
    _caption(sl, s)


def _kpi(prs, s: Dict[str, Any]) -> None:
    sl, y = _head(prs, s)
    items = _list(s, "kpis")[:MAX_KPI]
    if not items:
        k.tb(sl, Cm(1.3), y, Cm(39), Cm(1), "표시할 수치가 없다", size=13, color=k.MUTE)
    w, gap = Cm(9.4), Cm(0.6)
    for n, one in enumerate(items):
        k.kpi_card(sl, Cm(1.3) + (w + gap) * n, y, w, Cm(4.4),
                   _s(one, "label"), _s(one, "value"), _s(one, "sub"))
    _caption(sl, s, dropped=len(_list(s, "kpis")) - len(items), unit="칸")


def _cards(prs, s: Dict[str, Any]) -> None:
    sl, y = _head(prs, s)
    items = _list(s, "cards")[:MAX_CARDS]
    if not items:
        k.tb(sl, Cm(1.3), y, Cm(39), Cm(1), "표시할 카드가 없다", size=13, color=k.MUTE)
    n = max(len(items), 1)
    gap = Cm(0.6)
    w = int((k.A3_W - Cm(2.6) - gap * (n - 1)) / n)
    for i, one in enumerate(items):
        x = Cm(1.3) + (w + gap) * i
        k.rect(sl, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, Cm(9.4), fill=k.PANEL)
        k.rect(sl, MSO_SHAPE.RECTANGLE, x, y + Cm(0.3), Cm(0.12), Cm(8.8), fill=k.RED)
        k.tb(sl, x + Cm(0.6), y + Cm(0.5), w - Cm(1.0), Cm(1.2), _s(one, "head"),
             size=20, color=k.WHITE, bold=True)
        if _s(one, "tag"):
            k.tb(sl, x + Cm(0.6), y + Cm(1.9), w - Cm(1.0), Cm(1.0), _s(one, "tag"),
                 size=11, color=k.MUTE)
        k.tb(sl, x + Cm(0.6), y + Cm(3.1), w - Cm(1.0), Cm(6.0), _s(one, "body"),
             size=12, color=k.WHITE)
    _caption(sl, s, dropped=len(_list(s, "cards")) - len(items), unit="장")


def _table(prs, s: Dict[str, Any]) -> None:
    sl, y = _head(prs, s)
    headers = [str(h) for h in _list(s, "headers")]
    rows = [[("" if c is None else str(c)) for c in row] for row in _list(s, "rows")]
    if not headers or not rows:
        k.tb(sl, Cm(1.3), y, Cm(39), Cm(1), "표시할 표가 없다", size=13, color=k.MUTE)
        _caption(sl, s)
        return
    shown, dropped = rows[:MAX_ROWS], max(len(rows) - MAX_ROWS, 0)
    ratios = _list(s, "ratios") or None
    if ratios and len(ratios) != len(headers):
        ratios = None                       # 열 수와 안 맞으면 안 쓴다 — 표가 어긋난다
    k.table(sl, Cm(1.3), y, k.A3_W - Cm(2.6), headers, shown, ratios=ratios)
    _caption(sl, s, dropped=dropped, unit="줄")


def _text(prs, s: Dict[str, Any]) -> None:
    sl, y = _head(prs, s)
    lines: List[str] = []
    if _s(s, "lead"):
        lines.append(_s(s, "lead"))
    lines += [str(x) for x in _list(s, "body")]
    k.tb(sl, Cm(1.3), y, k.A3_W - Cm(2.6), Cm(16), lines or ["내용이 없다"],
         size=13, color=k.WHITE)
    _caption(sl, s)


_DRAWERS = {"cover": _cover, "kpi": _kpi, "cards": _cards, "table": _table, "text": _text}


# ── 잔손질 ──────────────────────────────────────────────────────────────────


def _head(prs, s: Dict[str, Any]):
    """제목 + 소제목. 돌려주는 y 는 **본문이 시작하는 높이**다."""
    sl = k.blank_slide(prs)
    k.bracket_title(sl, _s(s, "title"), _s(s, "subtitle"))
    y = Cm(3.4) if _s(s, "subtitle") else Cm(2.9)
    if _s(s, "lead") and s.get("kind") != "text":
        k.tb(sl, Cm(1.3), y, k.A3_W - Cm(2.6), Cm(1.2), _s(s, "lead"), size=15, color=k.WHITE)
        y += Cm(1.6)
    return sl, y


def _caption(sl, s: Dict[str, Any], *, dropped: int = 0, unit: str = "") -> None:
    """캡션 밴드 — 보낸 쪽의 말 + **근거 번호** + 자른 것.

    근거를 찍는 이유는 PPTX 에 `data-ev` 를 못 달아서다. 장표만 들고 심의에 가도
    「그 숫자 어디서 났습니까」에 답할 수 있어야 한다.
    """
    runs: List[tuple] = []
    if _s(s, "caption"):
        runs.append((_s(s, "caption"), None, True))
    sources = [str(x) for x in _list(s, "sources")]
    if sources:
        if runs:
            runs.append(("   ", None, False))
        runs.append((f"근거 {' · '.join(sources[:14])}"
                     + (f" 외 {len(sources) - 14}건" if len(sources) > 14 else ""),
                     None, False))
    if dropped > 0:
        runs.append((f"   ⚠ {dropped}{unit} 은 자리가 없어 뺐습니다", None, True))
    if runs:
        k.caption_band(sl, runs)


def _s(d: Any, key: str) -> str:
    got = d.get(key) if isinstance(d, dict) else getattr(d, key, None)
    return "" if got is None else str(got)


def _list(d: Any, key: str) -> List[Any]:
    got = d.get(key) if isinstance(d, dict) else getattr(d, key, None)
    return list(got) if isinstance(got, list) else []
