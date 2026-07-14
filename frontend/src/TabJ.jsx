import { useState } from "react";
import { contextPack, contextPackPptx } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes } from "./ui.jsx";

const RADII = [500, 1000, 2000];
const SECTIONS = [
  ["survey", "행정동 인구·세대 (걸침 합산)"],
  ["facilities", "시설 현황 (도서관·경로당·어린이집)"],
  ["quota", "총량제 부족/충족 판정"],
];
const FACILITIES = ["작은도서관", "경로당", "어린이집", "다함께돌봄센터"];

const verdictTone = (v) =>
  v === "부족시설" ? "amber" : v === "충족시설" ? "green" : "slate";

const lbl = {
  color: "var(--mute)", fontSize: 11, fontFamily: "var(--font-mono)",
  letterSpacing: "0.06em", textTransform: "uppercase",
};

// "409, 581" → [409, 581] / "981" → 981 / 숫자 아닌 토큰 있으면 "invalid"
function parseHouseholds(s) {
  const toks = s.split(",").map((x) => x.trim()).filter((x) => x.length > 0);
  if (toks.length === 0) return null;
  if (!toks.every((t) => /^\d+$/.test(t))) return "invalid";  // "409x"·"foo" 조용히 삼키지 않음
  const nums = toks.map((t) => parseInt(t, 10)).filter((n) => n > 0);
  if (nums.length === 0) return null;
  return nums.length === 1 ? nums[0] : nums;
}

// "작은도서관:1000.16, 경로당:3015" → {작은도서관:1000.16, ...}
function parseAreas(s) {
  const out = {};
  s.split(",").forEach((pair) => {
    const [k, v] = pair.split(":").map((x) => (x || "").trim());
    const f = parseFloat(v);
    if (k && !isNaN(f)) out[k] = f;
  });
  return Object.keys(out).length ? out : null;
}

export default function TabJ({ address }) {
  const [households, setHouseholds] = useState("");
  const [radius, setRadius] = useState(1000);
  const [existing, setExisting] = useState("");
  const [planned, setPlanned] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [show, setShow] = useState({ survey: true, facilities: true, quota: true });
  const [loading, setLoading] = useState(false);
  const [pptxLoading, setPptxLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [pptxUrl, setPptxUrl] = useState(null);

  function validate() {
    if (!address.trim()) { setError({ message: "주소를 먼저 입력하세요." }); return null; }
    const hh = parseHouseholds(households);
    if (hh === "invalid") { setError({ message: "세대수는 숫자만 입력하세요 (다획지는 예: 409, 581)." }); return null; }
    if (!hh) { setError({ message: "신축 세대수를 입력하세요 (다획지는 예: 409, 581)." }); return null; }
    // 고급 면적은 입력했는데 형식이 틀려 하나도 못 읽으면 알려줌 (조용히 무시하지 않음)
    if (advanced && existing.trim() && !parseAreas(existing)) {
      setError({ message: "기존시설 면적 형식: 시설명:숫자, … (예: 작은도서관:1000)" }); return null;
    }
    if (advanced && planned.trim() && !parseAreas(planned)) {
      setError({ message: "계획 면적 형식: 시설명:숫자, … (예: 작은도서관:515)" }); return null;
    }
    return hh;
  }

  async function run() {
    const hh = validate(); if (!hh) return;
    setLoading(true); setError(null); setData(null); setPptxUrl(null);
    try {
      setData(await contextPack(address, hh, radius, parseAreas(existing), parseAreas(planned)));
    } catch (e) { setError(e); } finally { setLoading(false); }
  }

  async function download() {
    const hh = validate(); if (!hh) return;
    setPptxLoading(true); setError(null);
    try {
      const r = await contextPackPptx(address, hh, radius, parseAreas(existing), parseAreas(planned));
      setPptxUrl(r.url);
      window.open(r.url, "_blank", "noopener");
    } catch (e) { setError(e); } finally { setPptxLoading(false); }
  }

  const sv = data?.survey;
  return (
    <div>
      <p className="text-sm mb-4" style={{ color: "var(--mute)" }}>
        서울시 통합심의 <b>커뮤니티 총량제 검토</b>를 자동 산정 — 조사범위 걸침 인구·세대,
        주변 시설 현황, 주민공동시설 부족/충족 판정. 부족/충족은{" "}
        <span style={{ color: "var(--warn)", fontWeight: 500 }}>참고</span> — 최종 확정은 사람이(생활권 범위·조례 tier).
      </p>

      {/* 입력 */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <span className="block mb-1.5" style={lbl}>신축 세대수 (설계)</span>
          <input value={households} onChange={(e) => setHouseholds(e.target.value)}
            placeholder="예) 981  ·  다획지 409, 581"
            className="w-full px-3 py-2 focus:outline-none"
            style={{ border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", fontSize: 14, background: "var(--canvas-elevated)", color: "var(--ink)" }} />
        </div>
        <div>
          <span className="block mb-1.5" style={lbl}>조사범위 반경 (m)</span>
          <div className="flex gap-2">
            {RADII.map((r) => (
              <button key={r} onClick={() => setRadius(r)} className="px-3 py-2 text-sm"
                style={{ border: radius === r ? "1px solid var(--brand)" : "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", background: radius === r ? "var(--brand)" : "var(--canvas-elevated)", color: radius === r ? "#fff" : "var(--body)" }}>
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 고급: 기존/계획 면적 */}
      <button onClick={() => setAdvanced(!advanced)} className="text-xs mb-2"
        style={{ color: "var(--mute)", fontFamily: "var(--font-mono)" }}>
        {advanced ? "▾" : "▸"} 기존시설·계획 면적 입력 (총량제 판정 완성 — 선택)
      </button>
      {advanced && (
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <span className="block mb-1.5" style={lbl}>기존시설 면적 (조사)</span>
            <input value={existing} onChange={(e) => setExisting(e.target.value)}
              placeholder="작은도서관:1000, 경로당:3015, 어린이집:5728"
              className="w-full px-3 py-2 text-xs focus:outline-none"
              style={{ border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", background: "var(--canvas-elevated)", color: "var(--ink)" }} />
          </div>
          <div>
            <span className="block mb-1.5" style={lbl}>계획 면적 (설계)</span>
            <input value={planned} onChange={(e) => setPlanned(e.target.value)}
              placeholder="작은도서관:515, 경로당:355, 어린이집:431"
              className="w-full px-3 py-2 text-xs focus:outline-none"
              style={{ border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", background: "var(--canvas-elevated)", color: "var(--ink)" }} />
          </div>
        </div>
      )}

      {/* 포함 항목 체크리스트 */}
      <div className="mb-4">
        <span className="block mb-1.5" style={lbl}>포함 항목 (미리보기)</span>
        <div className="flex flex-wrap gap-3">
          {SECTIONS.map(([key, label]) => (
            <label key={key} className="flex items-center gap-1.5 text-sm" style={{ color: "var(--body)" }}>
              <input type="checkbox" checked={show[key]}
                onChange={(e) => setShow({ ...show, [key]: e.target.checked })} />
              {label}
            </label>
          ))}
        </div>
      </div>

      {/* 버튼 */}
      <div className="flex gap-2 mb-5">
        <button onClick={run} disabled={loading}
          className="px-4 py-2 text-sm font-medium"
          style={{ background: "var(--brand)", color: "#fff", borderRadius: "var(--radius-sm)", opacity: loading ? 0.6 : 1 }}>
          {loading ? "산정 중…" : "산정하기"}
        </button>
        <button onClick={download} disabled={pptxLoading}
          className="px-4 py-2 text-sm font-medium"
          style={{ border: "1px solid var(--brand)", color: "var(--brand)", borderRadius: "var(--radius-sm)", background: "var(--canvas-elevated)", opacity: pptxLoading ? 0.6 : 1 }}>
          {pptxLoading ? "PPTX 생성 중…" : "A3 PPTX 내려받기 ↓"}
        </button>
      </div>

      {loading && <Spinner label="걸침 합산·시설 조사·총량제 산정 중…" />}
      <ErrorBox error={error} />
      {pptxUrl && (
        <p className="text-sm mb-4">
          ✅ 생성됨 —{" "}
          <a href={pptxUrl} target="_blank" rel="noreferrer" style={{ color: "var(--brand)", textDecoration: "underline" }}>
            심의 현황팩 A3 PPTX 열기 ↗
          </a>
          <span style={{ color: "var(--mute)", fontSize: 12 }}> (편집가능 표·위치도 — 심의도서에 드롭 후 손질)</span>
        </p>
      )}

      {data && (
        <div className="space-y-6">
          <div className="text-xs" style={{ color: "var(--mute)", fontFamily: "var(--font-mono)" }}>
            {sv?.site_sgg} · {data.ym?.slice(0, 4)}.{data.ym?.slice(4)} 기준 · 걸침 적용세대 {sv?.applied_hh_total?.toLocaleString()}
            {data.gu_infant ? ` · 구 영유아 ${data.gu_infant.toLocaleString()} / 세대 ${data.gu_households?.toLocaleString()}` : ""}
          </div>

          {/* 걸침 인구·세대표 */}
          {show.survey && sv && (
            <section>
              <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--ink)" }}>조사대상 행정동 인구·세대 (걸침 합산)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--hairline)", color: "var(--mute)", fontSize: 12 }}>
                      <th className="text-left py-1.5">행정동</th><th className="text-right">총인구</th>
                      <th className="text-right">총세대</th><th className="text-right">걸침율</th>
                      <th className="text-right">적용인구</th><th className="text-right">적용세대</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sv.dongs.map((d, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--hairline-soft, #eee)", opacity: d.flagged ? 0.6 : 1 }}>
                        <td className="py-1.5">{d.name}{d.flagged && <span style={{ color: "var(--warn)" }}> ⚠</span>}</td>
                        <td className="text-right">{d.total_pop?.toLocaleString() ?? "—"}</td>
                        <td className="text-right">{d.total_hh?.toLocaleString() ?? "—"}</td>
                        <td className="text-right">{(d.ratio * 100).toFixed(2)}%</td>
                        <td className="text-right">{d.applied_pop?.toLocaleString() ?? "—"}</td>
                        <td className="text-right">{d.applied_hh?.toLocaleString() ?? "—"}</td>
                      </tr>
                    ))}
                    <tr style={{ fontWeight: 600, background: "var(--canvas-sunken, #f6f7fb)" }}>
                      <td className="py-1.5">계 (대지 시군구)</td><td className="text-right">{sv.applied_pop_total.toLocaleString()}</td>
                      <td className="text-right">{sv.applied_hh_total.toLocaleString()}</td><td></td>
                      <td className="text-right">{sv.applied_pop_total.toLocaleString()}</td><td className="text-right">{sv.applied_hh_total.toLocaleString()}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="text-xs mt-1" style={{ color: "var(--mute)" }}>⚠ 타 시군구 동은 생활권 검토 필요 — '계'에서 제외. 걸침율=면적 교차비율.</p>
            </section>
          )}

          {/* 시설 현황 */}
          {show.facilities && data.facilities?.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--ink)" }}>조사범위 내 시설 현황</h3>
              <div className="grid grid-cols-3 gap-3">
                {data.facilities.map((c) => (
                  <div key={c.category} className="p-3" style={{ border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)" }}>
                    <div className="flex items-baseline justify-between mb-1">
                      <span className="text-sm font-medium">{c.category}</span>
                      <span className="text-sm" style={{ color: "var(--brand)" }}>{c.count}개</span>
                    </div>
                    {c.capacity ? <div className="text-xs" style={{ color: "var(--mute)" }}>정원 {c.capacity}명 ({c.capacity_scope})</div> : null}
                    <ul className="mt-1 text-xs" style={{ color: "var(--body)" }}>
                      {c.items.slice(0, 4).map((it, i) => (
                        <li key={i} className="truncate">· {it.name} <span style={{ color: "var(--mute)" }}>{it.dist_m}m</span></li>
                      ))}
                      {c.count > 4 && <li style={{ color: "var(--mute)" }}>… 외 {c.count - 4}개</li>}
                    </ul>
                  </div>
                ))}
              </div>
              <p className="text-xs mt-1" style={{ color: "var(--mute)" }}>면적(㎡)은 개별 출처 미제공 — 목록·개수만.</p>
            </section>
          )}

          {/* 총량제 판정 */}
          {show.quota && data.results?.map((res, ri) => (
            <section key={ri}>
              <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--ink)" }}>
                커뮤니티 총량제 검토{res.label ? ` — ${res.label}` : ""} <span className="font-normal" style={{ color: "var(--mute)", fontSize: 12 }}>(신축 {res.new_households.toLocaleString()}세대)</span>
              </h3>
              <div className="space-y-1.5">
                {res.facilities.map((f, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm p-2" style={{ border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)" }}>
                    <span className="font-medium" style={{ minWidth: 90 }}>{f.name}</span>
                    <Badge tone={verdictTone(f.verdict)}>{f.verdict}</Badge>
                    <span style={{ color: "var(--mute)", fontSize: 12 }}>
                      {f.required_area != null ? `산출 ${f.required_area.toLocaleString()}㎡` : "면적기준"}
                      {f.legal_min != null ? ` · 법정 ${f.legal_min}㎡` : ""}
                      {f.legal_min_confidence === "low" ? " ⚠조례확인" : ""}
                    </span>
                    {f.plan_ok != null && (
                      <span style={{ marginLeft: "auto", color: f.plan_ok ? "var(--ok, #2e7d32)" : "var(--warn)", fontSize: 12 }}>
                        계획 {f.plan_ok ? "충족" : "미달"} ({f.plan_diff > 0 ? "+" : ""}{f.plan_diff}㎡)
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </section>
          ))}

          <Notes notes={data.notes} />
        </div>
      )}
    </div>
  );
}
