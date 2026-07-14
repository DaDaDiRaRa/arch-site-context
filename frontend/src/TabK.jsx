import { useState } from "react";
import { surroundings, surroundingsPptx } from "./api.js";
import { Spinner, ErrorBox, Notes } from "./ui.jsx";

const RADII = [500, 1000, 2000];
const lbl = {
  color: "var(--mute)", fontSize: 11, fontFamily: "var(--font-mono)",
  letterSpacing: "0.06em", textTransform: "uppercase",
};

const rgb = (c) => `rgb(${c[0]},${c[1]},${c[2]})`;

export default function TabK({ address }) {
  const [radius, setRadius] = useState(1000);
  const [loading, setLoading] = useState(false);
  const [pptxLoading, setPptxLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [pptxUrl, setPptxUrl] = useState(null);

  async function run() {
    if (!address.trim()) return setError({ message: "주소를 먼저 입력하세요." });
    setLoading(true); setError(null); setData(null); setPptxUrl(null);
    try {
      setData(await surroundings(address, radius));
    } catch (e) { setError(e); } finally { setLoading(false); }
  }

  async function download() {
    if (!address.trim()) return setError({ message: "주소를 먼저 입력하세요." });
    setPptxLoading(true); setError(null);
    try {
      const r = await surroundingsPptx(address, radius);
      setPptxUrl(r.url);
      window.open(r.url, "_blank");
    } catch (e) { setError(e); } finally { setPptxLoading(false); }
  }

  return (
    <div>
      <p className="text-sm mb-4" style={{ color: "var(--mute)" }}>
        심의 <b>주변현황도</b> (슬라이드 4~6) — 대지 반경 내 여가·교육·주거·관공서·교통 시설을
        카테고리별로 수집하고 현황 서술문을 조립합니다. 도로폭·재개발 경계는 소스 미확보로 표기하지 않습니다.
      </p>

      <div className="mb-4">
        <span className="block mb-1.5" style={lbl}>조사 반경 (m)</span>
        <div className="flex gap-2">
          {RADII.map((r) => (
            <button key={r} onClick={() => setRadius(r)} className="px-3 py-2 text-sm"
              style={{ border: radius === r ? "1px solid var(--brand)" : "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", background: radius === r ? "var(--brand)" : "var(--canvas-elevated)", color: radius === r ? "#fff" : "var(--body)" }}>
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2 mb-5">
        <button onClick={run} disabled={loading} className="px-4 py-2 text-sm font-medium"
          style={{ background: "var(--brand)", color: "#fff", borderRadius: "var(--radius-sm)", opacity: loading ? 0.6 : 1 }}>
          {loading ? "조사 중…" : "주변현황 조사"}
        </button>
        <button onClick={download} disabled={pptxLoading} className="px-4 py-2 text-sm font-medium"
          style={{ border: "1px solid var(--brand)", color: "var(--brand)", borderRadius: "var(--radius-sm)", background: "var(--canvas-elevated)", opacity: pptxLoading ? 0.6 : 1 }}>
          {pptxLoading ? "PPTX 생성 중…" : "현황도 A3 PPTX ↓"}
        </button>
      </div>

      {loading && <Spinner label="반경 내 시설 수집 중…" />}
      <ErrorBox error={error} />
      {pptxUrl && (
        <p className="text-sm mb-4">
          ✅ <a href={pptxUrl} target="_blank" rel="noreferrer" style={{ color: "var(--brand)", textDecoration: "underline" }}>주변현황도 A3 PPTX 열기 ↗</a>
          <span style={{ color: "var(--mute)", fontSize: 12 }}> (위성 현황도 + 시설표 + 서술문)</span>
        </p>
      )}

      {data && (
        <div className="space-y-5">
          {/* 서술문 */}
          <section className="p-3" style={{ border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)", background: "var(--canvas-sunken, #f6f7fb)" }}>
            <span className="block mb-1" style={lbl}>주변현황 서술 (자동 조립)</span>
            <p className="text-sm" style={{ color: "var(--ink)", lineHeight: 1.6 }}>{data.narrative}</p>
          </section>

          {/* 카테고리 표 */}
          <section>
            <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--ink)" }}>주변시설 현황</h3>
            <div className="space-y-2">
              {data.categories.map((c) => (
                <div key={c.name} className="flex items-start gap-3 text-sm">
                  <span className="px-2 py-0.5 text-xs font-medium" style={{ background: rgb(c.color), color: "#fff", borderRadius: 4, minWidth: 54, textAlign: "center" }}>{c.name}</span>
                  <span style={{ color: "var(--brand)", minWidth: 40 }}>{c.count}개</span>
                  <span style={{ color: "var(--body)" }}>
                    {c.items.slice(0, 6).map((it) => it.name).join(", ")}{c.count > 6 ? " 등" : ""}
                  </span>
                </div>
              ))}
            </div>
            <p className="text-xs mt-2" style={{ color: "var(--mute)" }}>반경밴드 {data.ring_radii?.join(" · ")}m · 카카오 검색(카테고리 코드 정제)</p>
          </section>

          <Notes notes={data.notes} />
        </div>
      )}
    </div>
  );
}
