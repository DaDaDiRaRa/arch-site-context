// 활성 탭의 결과 패널을 자체완결 HTML 한 장으로 다운로드 (모든 탭 공용).
// 앱의 동일 오리진 스타일시트(Tailwind+토큰)를 인라인해 오프라인에서도 스타일 유지.
// 위성 등 /files 상대 URL 이미지는 오프라인에선 안 뜰 수 있음(참고) — 표·수치·서술은 그대로.

export function downloadResultHtml(el, title = "결과") {
  if (!el) {
    alert("먼저 분석을 실행해 결과를 만든 뒤 저장하세요.");
    return;
  }
  // 동일 오리진 CSS 규칙 수집 (cross-origin 시트는 접근 불가 → skip)
  let css = "";
  for (const sheet of document.styleSheets) {
    try {
      for (const rule of sheet.cssRules) css += rule.cssText + "\n";
    } catch {
      /* cross-origin stylesheet — 건너뜀 */
    }
  }
  const stamp = new Date().toISOString().slice(0, 10);
  const safe = String(title).replace(/[\\/:*?"<>|]/g, "_");
  const doc = `<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>터읽기 · ${safe}</title>
<style>${css}
body{margin:0;padding:24px;background:var(--canvas-elevated,#fff);color:var(--ink,#111);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
.__wrap{max-width:1000px;margin:0 auto}
.__wrap button,.__wrap input,.__wrap select{pointer-events:none}
</style></head>
<body><div class="__wrap">
<h1 style="font-size:20px;font-weight:600;margin:0 0 2px">터읽기 · ${safe}</h1>
<p style="color:#888;font-size:12px;margin:0 0 16px">생성 ${stamp} · 통계 시군구 평균(KOSIS) · 수치는 코드/규칙, 표현만 AI · 최종 판단은 사람</p>
${el.innerHTML}
</div></body></html>`;
  const blob = new Blob([doc], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `터읽기_${safe}_${stamp}.html`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
