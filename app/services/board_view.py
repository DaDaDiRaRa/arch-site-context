"""T4 — 대지분석 보드 렌더 (자체완결 HTML). /board 결과 → 공유·인쇄 가능한 한 장.

임원·실무자·제안서가 "믿고 쓰는" 형태. 리서치 결론(대지분석의 종착점 = 편집된 한 장 보드)을
따른다: 지도 앵커 → 설계 드라이버 → 사실 종합 → 지수·근접도 → 출처 각인. 새 데이터 0 —
BoardResult 를 렌더만 (절대 원칙 1·2). CSP-safe·오프라인(외부 폰트·스크립트·이미지 링크 없음).

앱 프론트(TabI)와 같은 건원 디자인 토큰. 모드 B 위성 PNG 는 있으면 상단에 data URI 로 임베드
(지도가 신뢰의 앵커 — 한국 실무자 기대치), 없으면 graceful 생략.
"""

from __future__ import annotations

import html
from typing import Any, Optional


def _g(o: Any, k: str, d: Any = None) -> Any:
    if o is None:
        return d
    if isinstance(o, dict):
        return o.get(k, d)
    return getattr(o, k, d)


def _e(s: Any) -> str:
    return html.escape(str(s)) if s is not None else ""


def _prox_chip(p: Optional[str]) -> str:
    if not p:
        return ""
    tone = {"대지": "green", "반경": "green", "읍면동": "blue", "시군구": "slate", "proxy": "amber"}.get(p, "slate")
    return f'<span class="chip {tone}">{_e(p)}</span>'


def _index_bar(idx: Optional[int]) -> str:
    if idx is None:
        return '<span class="dash">—</span>'
    LO, HI = 40, 160
    clamp = lambda v: max(LO, min(HI, v))
    pct = lambda v: (clamp(v) - LO) / (HI - LO) * 100
    c, v = pct(100), pct(idx)
    left, width = min(c, v), abs(v - c)
    return (f'<span class="ibar"><span class="track">'
            f'<span class="center" style="left:{c:.1f}%"></span>'
            f'<span class="fill" style="left:{left:.1f}%;width:{width:.1f}%"></span></span>'
            f'<span class="ival">{idx}</span></span>')


def _fmt(v: Any, unit: str) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, int) and abs(v) >= 1000:
        return f"{v:,}{_e(unit)}"
    return f"{_e(v)}{_e(unit)}"


_CSS = """:root{--canvas:#fafafa;--elev:#fff;--ink:#171717;--body:#4d4d4d;--mute:#8f8f8f;--hairline:#ebebeb;
--brand:#E60012;--ok:#2ea043;--warn:#f5a623;--r:12px;--rs:6px;
--mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,monospace;
--sans:-apple-system,"Segoe UI",system-ui,Roboto,sans-serif;}
*{box-sizing:border-box}
body{margin:0;background:var(--canvas);color:var(--ink);font-family:var(--sans);line-height:1.5;
-webkit-font-smoothing:antialiased;font-size:14px}
.page{max-width:900px;margin:0 auto;padding:28px 20px 60px}
header{margin-bottom:20px}
.wm{font-size:22px;font-weight:600;letter-spacing:-.02em}
.wm .dot{color:var(--brand)} .wm-sub{font-size:15px;font-weight:400;color:var(--mute);margin-left:6px}
.meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.tag{font-family:var(--mono);font-size:11px;padding:3px 9px;border:1px solid var(--hairline);border-radius:999px;background:var(--elev);color:var(--body)}
.tag.brand{color:var(--brand);border-color:var(--brand)}
.sat{margin-top:16px;border:1px solid var(--hairline);border-radius:var(--r);overflow:hidden;background:var(--elev)}
.sat img{display:block;width:100%;height:auto}
.sat-cap{font-family:var(--mono);font-size:10.5px;color:var(--mute);padding:6px 10px;border-top:1px solid var(--hairline)}
section{margin-top:26px}
.arch{border:1px solid var(--brand);border-radius:var(--r);padding:14px 16px;background:linear-gradient(0deg,#fff,#fff)}
.arch-h{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:5px}
.arch-g{font-family:var(--mono);font-size:11px;color:var(--brand);border:1px solid var(--brand);border-radius:999px;padding:2px 9px}
.arch-n{font-size:18px;font-weight:700;color:var(--ink);letter-spacing:-.01em}
.arch-d{margin:0 0 8px;font-size:13.5px;color:var(--body)}
.arch-alt{margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--mute)}
.pgroups{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}
.pgroup{border:1px solid var(--hairline);border-radius:var(--r);padding:12px 14px;background:var(--elev)}
.pcat{font-family:var(--mono);font-size:11px;color:var(--brand);letter-spacing:.04em;margin-bottom:6px}
.plist{margin:0;padding-left:16px;display:flex;flex-direction:column;gap:5px}
.plist li{font-size:13px;color:var(--body)}
.pbasis{color:var(--mute);font-size:11px}
h2{font-size:14px;font-weight:600;color:var(--ink);margin:0 0 12px}
.h2-sub{font-weight:400;color:var(--mute)}
.cov-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
.cov{border:1px solid var(--hairline);border-left:3px solid var(--ok);border-radius:var(--rs);padding:9px 11px;background:var(--elev)}
.cov.warn{border-left-color:var(--warn)}
.cov-h{display:flex;justify-content:space-between;align-items:center;font-size:12px;font-weight:600}
.cov-s{font-size:11px;color:var(--ok)} .cov.warn .cov-s{color:var(--warn)}
.cov-d{font-size:11px;color:var(--mute);margin-top:3px}
.drivers,.walls,.crosses{display:flex;flex-direction:column;gap:10px}
.driver{border:1px solid var(--hairline);border-left:3px solid var(--brand);border-radius:var(--r);padding:13px 15px;background:var(--elev)}
.driver-h{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:5px}
.rank{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--brand)}
.driver-n{font-size:14px;font-weight:600;color:var(--ink)}
.strength{font-family:var(--mono);font-size:10px;color:var(--mute)}
.driver-r{margin:0 0 8px;font-size:13.5px;color:var(--body)}
.evs{display:flex;flex-direction:column;gap:3px}
.ev{display:flex;align-items:center;gap:7px;flex-wrap:wrap;font-size:12px;color:var(--mute)}
.ev-k{color:var(--body)} .ev-d{color:var(--ink);font-weight:500}
.wall{border:1px solid var(--hairline);border-radius:var(--r);padding:15px 17px;background:var(--elev)}
.wall.green{border-left:3px solid var(--ok)} .wall.amber{border:1px solid var(--warn);background:#fffdf7}
.wall-h{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.wall-t{font-size:14px;font-weight:600;color:var(--ink)}
.wall-note{margin:0 0 8px;font-size:11.5px;color:var(--warn)}
.wall-b{margin:0;font-size:13.5px;color:var(--body);white-space:pre-line;line-height:1.62}
.cross{border:1px solid var(--hairline);border-left:3px solid var(--warn);border-radius:var(--r);padding:11px 14px;background:var(--elev)}
.cross-h{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:3px}
.cross-n{font-size:13.5px;font-weight:600;color:var(--ink)}
.cross-t{margin:0;font-size:13px;color:var(--body)}
.twrap{overflow-x:auto;border:1px solid var(--hairline);border-radius:var(--r);background:var(--elev)}
table{width:100%;border-collapse:collapse;font-size:13px;min-width:640px}
thead{background:var(--canvas);color:var(--mute)}
th{text-align:left;font-weight:500;padding:8px 12px;font-size:12px;white-space:nowrap}
td{padding:8px 12px;border-top:1px solid var(--hairline);vertical-align:middle}
.num{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono)}
th.num{text-align:right}
.f-item{color:var(--body)} td.num{color:var(--ink);font-weight:600} td.num.mute{color:var(--mute);font-weight:400}
.src{font-size:11px;color:var(--mute);white-space:nowrap}
.ibar{display:inline-flex;align-items:center;gap:8px}
.track{position:relative;display:inline-block;width:72px;height:8px;background:var(--canvas);border:1px solid var(--hairline);border-radius:4px}
.center{position:absolute;top:-2px;bottom:-2px;width:1px;background:var(--ink)}
.fill{position:absolute;top:1px;bottom:1px;background:var(--brand);opacity:.5;border-radius:2px}
.ival{font-family:var(--mono);font-size:11px;color:var(--body)}
.dash{color:var(--hairline)}
.chip{display:inline-block;font-family:var(--mono);font-size:10.5px;padding:1px 8px;border-radius:999px;border:1px solid var(--hairline);background:var(--elev);color:var(--mute)}
.chip.green{color:var(--ok)} .chip.amber{color:var(--warn)} .chip.blue{color:var(--brand)} .chip.slate{color:var(--mute)}
.appx-sum{font-size:12.5px;color:var(--body);margin:0 0 12px;line-height:1.6}
.formulas{display:flex;flex-direction:column;gap:6px;margin-top:6px}
.formula{border:1px solid var(--hairline);border-radius:var(--rs);padding:8px 11px;background:var(--elev)}
.formula-i{font-size:12px;font-weight:600;color:var(--ink)}
.formula-f{font-family:var(--mono);font-size:12px;color:var(--brand)}
.formula-n{font-size:11px;color:var(--mute)}
.lims{margin:8px 0 0;padding-left:16px;display:flex;flex-direction:column;gap:4px}
.lims li{font-size:12px;color:var(--body)}
.appx-h3{font-size:12px;font-weight:600;color:var(--body);margin:14px 0 4px}
footer{margin-top:34px;padding-top:16px;border-top:1px solid var(--hairline);font-family:var(--mono);font-size:11px;color:var(--mute);line-height:1.7}
@media print{body{background:#fff}.page{max-width:none;padding:0}section{break-inside:avoid}}
@media(max-width:560px){.wm{font-size:19px}}"""


def render_board_html(board: Any, satellite_data_uri: Optional[str] = None,
                      massing_data_uri: Optional[str] = None) -> str:
    """BoardResult(또는 model_dump dict) → 자체완결 HTML 문서 문자열.

    massing_data_uri: arch-site-model 물리 모델 축측 미리보기(있으면 임베드 — 물리+인문 = 완전한 보드).
    """
    site = _g(board, "site") or {}
    reg = _g(board, "region") or {}
    parts: list = []

    # 헤더
    sat = ""
    if satellite_data_uri:
        sat = (f'<div class="sat"><img src="{_e(satellite_data_uri)}" alt="위성 사진">'
               f'<div class="sat-cap">위성: VWorld · 반경 {_g(board, "radius")}m · 대지 중심</div></div>')
    parts.append(f'''<header>
  <div class="wm">터읽기 <span class="dot">·</span> <span class="wm-sub">대지 종합 읽기</span></div>
  <div class="meta">
    <span class="tag brand">{_e(_g(site, "sigungu"))} {_e(_g(site, "eupmyeondong"))}</span>
    <span class="tag">{_e(_g(board, "use_type"))}</span>
    <span class="tag">반경 {_e(_g(board, "radius"))}m</span>
    <span class="tag">{_e(_g(reg, "name"))} 기준</span>
    <span class="tag">기준일 {_e(_g(board, "base_date"))}</span>
  </div>{sat}
</header>''')

    # 물리 모델 (arch-site-model) — 넘겨받은 경우만 (물리 3D + 인문 = 완전한 보드)
    model = _g(board, "model")
    if model:
        bc = _g(model, "building_count")
        rad_m = _g(model, "radius_m")
        cap = "물리 모델: arch-site-model · 축측 미리보기"
        if bc is not None:
            cap += f" · 건물 {_e(bc)}동"
        if rad_m:
            cap += f" · 반경 {_e(rad_m)}m"
        mimg = (f'<div class="sat"><img src="{_e(massing_data_uri)}" alt="물리 매싱 미리보기">'
                f'<div class="sat-cap">{cap}</div></div>') if massing_data_uri else ""
        bits = []
        if bc is not None:
            bits.append(f"건물 {_e(bc)}동")
        if _g(model, "solids") is not None:
            bits.append(f"솔리드 {_e(_g(model, 'solids'))}")
        if _g(model, "cadastral_parcels") is not None:
            bits.append(f"필지 {_e(_g(model, 'cadastral_parcels'))}")
        er = _g(model, "elev_range_m")
        if er and len(er) >= 2:
            bits.append(f"표고 {er[0]:.0f}~{er[1]:.0f}m")
        prov = _g(model, "provenance") or {}
        bsrc = prov.get("building_src") if isinstance(prov, dict) else None
        if bsrc:
            bits.append(f"출처 {_e(bsrc)}")
        files = _g(model, "files") or {}
        links = " · ".join(f'<a href="{_e(v)}">{_e(k)}</a>'
                           for k, v in files.items() if isinstance(v, str) and v.startswith("http"))
        note = _g(model, "note")
        parts.append(
            f'<section><h2>물리 모델 <span class="h2-sub">· arch-site-model 3D (건물·터레인·지적)</span></h2>'
            f'{mimg}<p class="appx-sum">{" · ".join(bits)}'
            + (f'<br>다운로드: {links}' if links else "")
            + (f'<br><span style="color:var(--mute)">{_e(note)}</span>' if note else "")
            + '</p></section>')

    # ★ 대지 아키타입 (동네 유형)
    arch = _g(board, "archetype")
    if arch:
        ev = "".join(f'<span class="ev"><span class="ev-k">{_e(_g(x, "key"))}</span>'
                     f'<span class="ev-d">{_e(_g(x, "detail"))}</span>{_prox_chip(_g(x, "proximity"))}</span>'
                     for x in (_g(arch, "evidence") or []))
        alts = _g(arch, "alternatives") or []
        alt = (f'<div class="arch-alt">차점 특성: {" · ".join(_e(a) for a in alts)}</div>') if alts else ""
        parts.append(f'''<section><div class="arch">
      <div class="arch-h"><span class="arch-g">{_e(_g(arch, "group"))}</span>
        <span class="arch-n">{_e(_g(arch, "name"))}</span><span class="chip amber">{_e(_g(arch, "tag", "참고"))}</span></div>
      <p class="arch-d">{_e(_g(arch, "description"))}</p>
      <div class="evs">{ev}</div>{alt}</div></section>''')

    # 커버리지
    cov = "".join(
        f'''<div class="cov {'ok' if _g(c, 'available') else 'warn'}">
      <div class="cov-h"><span>{_e(_g(c, 'domain'))}</span><span class="cov-s">{'확보' if _g(c, 'available') else '확인 불가'}</span></div>
      <div class="cov-d">{_e(_g(c, 'detail'))}</div></div>''' for c in (_g(board, "coverage") or []))
    if cov:
        parts.append(f'<section><h2>도메인 확보 현황</h2><div class="cov-grid">{cov}</div></section>')

    # ★ 설계 드라이버
    drivers = _g(board, "design_drivers") or []
    if drivers:
        drv = ""
        for d in drivers:
            ev = "".join(f'<div class="ev"><span class="ev-k">{_e(_g(x, "key"))}</span>'
                         f'<span class="ev-d">{_e(_g(x, "detail"))}</span>{_prox_chip(_g(x, "proximity"))}</div>'
                         for x in (_g(d, "evidence") or []))
            drv += f'''<div class="driver">
      <div class="driver-h"><span class="rank">#{_e(_g(d, 'rank'))}</span><span class="driver-n">{_e(_g(d, 'name'))}</span>
        <span class="strength">강도 {_e(_g(d, 'strength'))}</span><span class="chip amber">{_e(_g(d, 'tag', '참고'))}</span></div>
      <p class="driver-r">{_e(_g(d, 'response'))}</p><div class="evs">{ev}</div></div>'''
        parts.append(f'<section><h2>설계 드라이버 <span class="h2-sub">· 이 대지가 설계에 요구하는 것 (검토 신호·참고)</span></h2><div class="drivers">{drv}</div></section>')

    # ★ 프로그램 함의 (POR) — 카테고리별
    prog = _g(board, "program_implications") or []
    if prog:
        groups: list = []
        for it in prog:
            cat = _g(it, "category")
            if not groups or groups[-1][0] != cat:
                groups.append((cat, []))
            groups[-1][1].append(it)
        blocks = ""
        for cat, items in groups:
            lis = "".join(f'<li>{_e(_g(it, "recommendation"))}'
                          f'<span class="pbasis"> · {_e(" · ".join(_g(it, "basis") or []))}</span></li>'
                          for it in items)
            blocks += f'<div class="pgroup"><div class="pcat">{_e(cat)}</div><ul class="plist">{lis}</ul></div>'
        parts.append(f'<section><h2>프로그램 함의 <span class="h2-sub">· 카테고리별 공간·프로그램 권고 (POR·참고)</span></h2><div class="pgroups">{blocks}</div></section>')

    # S4 종합
    s = _g(board, "synthesis")
    if s:
        def _block(label, badge, tone, src, model, body, note=None):
            sb = "" if src == "ai" else f'<span class="chip slate">{"확인 불가" if src == "no_data" else "규칙 폴백"}</span>'
            mb = f'<span class="chip slate">{_e(model)}</span>' if model else ""
            nt = f'<p class="wall-note">⚠ {_e(note)}</p>' if note else ""
            return (f'<div class="wall {tone}"><div class="wall-h"><span class="wall-t">{label}</span>'
                    f'<span class="chip {tone}">{badge}</span>{sb}{mb}</div>{nt}<p class="wall-b">{_e(body)}</p></div>')
        i = _block("① 사실 종합", "검증된 사실 · 참고", "green", _g(s, "interpretation_source"),
                   _g(s, "interpretation_model"), _g(s, "interpretation"))
        j = _block("② AI 판단", "AI 의견 · 검증 보장 없음", "amber", _g(s, "judgment_source"),
                   _g(s, "judgment_model"), _g(s, "judgment"), note=_g(s, "judgment_label"))
        parts.append(f'<section><h2>종합 산출 <span class="h2-sub">· 사실과 AI 의견을 벽으로 분리</span></h2><div class="walls">{i}{j}</div></section>')

    # 교차 시사점
    cross = _g(board, "cross_implications") or []
    if cross:
        ci = ""
        for c in cross:
            doms = "".join(f'<span class="chip slate">{_e(x)}</span>' for x in (_g(c, "domains") or []))
            ci += f'<div class="cross"><div class="cross-h">{doms}<span class="cross-n">{_e(_g(c, "name"))}</span></div><p class="cross-t">{_e(_g(c, "text"))}</p></div>'
        parts.append(f'<section><h2>교차 시사점 <span class="h2-sub">· 도메인 횡단</span></h2><div class="crosses">{ci}</div></section>')

    # facts (전체 board 는 facts, brief 는 key_facts)
    facts = _g(board, "facts") or _g(board, "key_facts") or []
    if facts:
        rows = ""
        for f in facts:
            na = _g(f, "national_avg")
            na_txt = _fmt(na, _g(f, "unit", "")) if na is not None else "—"
            src = _g(f, "source_tbl") or _g(f, "source") or ""
            rows += (f'<tr><td class="f-item">{_e(_g(f, "item"))}</td>'
                     f'<td class="num">{_fmt(_g(f, "value"), _g(f, "unit", ""))}</td>'
                     f'<td class="num mute">{na_txt}</td>'
                     f'<td>{_index_bar(_g(f, "index"))}</td>'
                     f'<td>{_prox_chip(_g(f, "proximity"))}</td>'
                     f'<td class="src">{_e(src)} · {_e(_g(f, "year"))}</td></tr>')
        parts.append(f'''<section><h2>인구·통계 <span class="h2-sub">· 전국=100 지수 + 근접도</span></h2>
  <div class="twrap"><table><thead><tr><th>항목</th><th class="num">값</th><th class="num">전국 평균</th><th>전국 대비 (100)</th><th>근접도</th><th>출처·연도</th></tr></thead>
  <tbody>{rows}</tbody></table></div></section>''')

    # ★ T5 방법론·데이터 부록 — 출처·산정식·한계 각인 (공모·감사 대비)
    m = _g(board, "methodology")
    if m:
        srows = ""
        for s in _g(m, "sources") or []:
            used = " · ".join(_g(s, "used_for") or [])
            yrs = ", ".join(str(y) for y in (_g(s, "years") or []))
            srows += (f'<tr><td class="f-item">{_e(_g(s, "name"))}</td>'
                      f'<td class="src">{_e(_g(s, "publisher"))}</td>'
                      f'<td class="src">{_e(_g(s, "kind"))}</td>'
                      f'<td class="src">{_e(used)}</td>'
                      f'<td>{_prox_chip(_g(s, "proximity"))}</td>'
                      f'<td class="src">{_e(yrs)}</td></tr>')
        stbl = (f'<div class="twrap"><table><thead><tr><th>출처</th><th>기관</th><th>유형</th>'
                f'<th>기여 지표</th><th>근접도</th><th>연도</th></tr></thead>'
                f'<tbody>{srows}</tbody></table></div>') if srows else ""
        fblocks = "".join(
            f'<div class="formula"><span class="formula-i">{_e(_g(f, "item"))}</span> '
            f'<span class="formula-f">= {_e(_g(f, "formula"))}</span>'
            + (f'<div class="formula-n">{_e(_g(f, "note"))}</div>' if _g(f, "note") else "")
            + '</div>'
            for f in (_g(m, "formulas") or []))
        fbox = f'<div class="appx-h3">산정식</div><div class="formulas">{fblocks}</div>' if fblocks else ""
        lims = "".join(f'<li>{_e(x)}</li>' for x in (_g(m, "limitations") or []))
        lbox = f'<div class="appx-h3">한계·주의</div><ul class="lims">{lims}</ul>' if lims else ""
        parts.append(
            f'<section><h2>방법론·데이터 부록 <span class="h2-sub">· 사용 출처·산정식·한계 (공모·감사 대비)</span></h2>'
            f'<p class="appx-sum">{_e(_g(m, "summary"))}</p>'
            f'<div class="appx-h3">데이터 출처 <span class="h2-sub">· 이 보드에 실제로 기여한 것만</span></div>{stbl}'
            f'{fbox}{lbox}</section>')

    parts.append('<footer>통계: 시군구 평균(KOSIS·SGIS) · 시설: 카카오/VWorld · 대지: VWorld·건축HUB·국토부 · '
                 '수치는 코드·규칙, 표현만 AI · 실제 API 호출·출처 명시·판단은 사람</footer>')

    title = f"{_g(site, 'sigungu') or ''} {_g(site, 'eupmyeondong') or ''} 대지 종합 읽기".strip()
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_e(title)} · 터읽기</title><style>{_CSS}</style></head>'
            f'<body><div class="page">{"".join(parts)}</div></body></html>')
