import { useState } from "react";
import { readout } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes } from "./ui.jsx";

const TYPES = ["재건축", "재개발", "민간", "주상복합"];

function fmt(v) {
  if (typeof v === "number" && Number.isInteger(v) && Math.abs(v) >= 1000)
    return v.toLocaleString("ko-KR");
  return v;
}

// 강조 지표는 굵게+파란 배경, 일반은 회색.
function Row({ on, children }) {
  return (
    <div className={`flex items-baseline justify-between px-3 py-1.5 rounded ${on ? "bg-blue-50" : ""}`}>
      {children}
    </div>
  );
}

export default function TabH({ address }) {
  const [ptype, setPtype] = useState("재건축");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  async function run() {
    if (!address.trim()) { setError({ message: "주소를 먼저 입력하세요." }); return; }
    setLoading(true); setError(null); setData(null);
    try { setData(await readout(address, ptype)); }
    catch (e) { setError(e); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <p className="text-sm text-slate-500 mb-4">
        공동주택(재건축·재개발·민간) 부지의 시군구 인문·경제 맥락을 한 화면에. 유형에 따라{" "}
        <span className="text-blue-700 font-medium">★강조</span> 지표가 바뀝니다. 모두 시군구 평균 — 판단은 사람이.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="block text-slate-500 mb-1">프로젝트 유형</span>
          <div className="flex gap-1">
            {TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setPtype(t)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium border ${ptype === t ? "bg-blue-600 text-white border-blue-600" : "border-slate-300 text-slate-600 hover:bg-slate-50"}`}
              >
                {t}
              </button>
            ))}
          </div>
        </label>
        <button
          onClick={run}
          disabled={loading}
          className="px-4 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          대지 readout
        </button>
      </div>

      {loading && <Spinner label="인구·산업·주거·복지 종합 조회 중…" />}
      <div className="mt-4"><ErrorBox error={error} /></div>

      {data && (
        <div className="mt-5 space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="blue">{data.site.sigungu} 기준</Badge>
            <Badge>{data.project_type}</Badge>
            <Badge>{data.base_date}</Badge>
          </div>

          {/* 인구·가구 */}
          <section>
            <h3 className="text-sm font-semibold text-slate-700 mb-1.5">인구 · 가구</h3>
            <div className="rounded-lg border border-slate-200 divide-y divide-slate-100">
              {data.demographics.map((f, i) => (
                <Row key={i} on={f.emphasized}>
                  <span className="text-sm text-slate-700">
                    {f.emphasized && <span className="text-blue-600 mr-1">★</span>}{f.item}
                  </span>
                  <span className="text-sm">
                    <span className="font-semibold text-slate-900">{fmt(f.value)}{f.unit}</span>
                    {f.national_avg != null && (
                      <span className="text-slate-400"> · 전국 {fmt(f.national_avg)}{f.unit}</span>
                    )}
                  </span>
                </Row>
              ))}
            </div>
          </section>

          {/* 산업·주거·복지 */}
          <section>
            <h3 className="text-sm font-semibold text-slate-700 mb-1.5">산업 · 주거 · 복지</h3>
            <div className="rounded-lg border border-slate-200 divide-y divide-slate-100">
              {data.context.map((c, i) => (
                <div key={i} className={`px-3 py-1.5 ${c.emphasized ? "bg-blue-50" : ""}`}>
                  <div className="flex items-baseline justify-between">
                    <span className="text-sm text-slate-700">
                      {c.emphasized && <span className="text-blue-600 mr-1">★</span>}{c.label}
                      <span className="text-slate-400 text-xs ml-1">[{c.axis}]</span>
                    </span>
                    <span className="text-sm font-semibold text-slate-900">
                      {c.value != null ? `${fmt(c.value)}${c.unit}` : "—"}
                    </span>
                  </div>
                  {c.breakdown?.length > 0 && (
                    <div className="text-xs text-slate-500 mt-0.5">
                      {c.breakdown.slice(0, 4).map(([nm, v]) => `${nm} ${fmt(v)}`).join(" · ")}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>

          {/* 파생지표 */}
          {data.derived.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-slate-700 mb-1.5">파생지표</h3>
              <div className="flex flex-wrap gap-2">
                {data.derived.map((d, i) => (
                  <div key={i} className="rounded-lg border border-slate-200 px-3 py-2">
                    <div className="text-xs text-slate-500">{d.label}</div>
                    <div className="text-lg font-bold text-slate-900">
                      {fmt(d.value)}<span className="text-xs font-normal text-slate-500 ml-0.5">{d.unit}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <Notes notes={data.notes} />
        </div>
      )}
    </div>
  );
}
