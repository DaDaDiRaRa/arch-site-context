import { useState } from "react";
import { readout } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes } from "./ui.jsx";

const TYPES = ["재건축", "재개발", "민간", "주상복합"];

function fmt(v) {
  if (typeof v === "number" && Number.isInteger(v) && Math.abs(v) >= 1000)
    return v.toLocaleString("ko-KR");
  return v;
}

function Row({ on, first, children }) {
  return (
    <div
      className="flex items-baseline justify-between px-3 py-1.5"
      style={{
        borderTop: first ? 'none' : '1px solid var(--hairline)',
        borderLeft: on ? '3px solid var(--brand)' : '3px solid transparent',
        background: on ? 'var(--canvas)' : 'transparent',
      }}
    >
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
      <p className="text-sm mb-4" style={{color:'var(--mute)'}}>
        공동주택(재건축·재개발·민간) 부지의 시군구 인문·경제 맥락을 한 화면에. 유형에 따라{" "}
        <span style={{color:'var(--brand)',fontWeight:500}}>★강조</span> 지표가 바뀝니다. 모두 시군구 평균 — 판단은 사람이.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span
            className="block mb-1"
            style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
          >
            프로젝트 유형
          </span>
          <div className="flex gap-1">
            {TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setPtype(t)}
                className="px-3 py-1.5 text-sm font-medium"
                style={{
                  border: ptype === t ? '1px solid var(--brand)' : '1px solid var(--hairline)',
                  borderRadius: 'var(--radius-sm)',
                  background: ptype === t ? 'var(--brand)' : 'var(--canvas-elevated)',
                  color: ptype === t ? '#fff' : 'var(--body)',
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </label>
        <button
          onClick={run}
          disabled={loading}
          className="px-4 py-2 font-medium disabled:opacity-50"
          style={{background:'var(--brand)',color:'#fff',borderRadius:'var(--radius-sm)'}}
          onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background='var(--brand-hover)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background='var(--brand)'; }}
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
            <h3 className="text-sm font-semibold mb-1.5" style={{color:'var(--body)'}}>인구 · 가구</h3>
            <div style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius)'}}>
              {data.demographics.map((f, i) => (
                <Row key={i} on={f.emphasized} first={i === 0}>
                  <span className="text-sm" style={{color:'var(--body)'}}>
                    {f.emphasized && <span style={{color:'var(--brand)'}} className="mr-1">★</span>}{f.item}
                  </span>
                  <span className="text-sm">
                    <span className="font-semibold" style={{color:'var(--ink)'}}>{fmt(f.value)}{f.unit}</span>
                    {f.national_avg != null && (
                      <span style={{color:'var(--mute)'}}> · 전국 {fmt(f.national_avg)}{f.unit}</span>
                    )}
                  </span>
                </Row>
              ))}
            </div>
          </section>

          {/* 산업·주거·복지 */}
          <section>
            <h3 className="text-sm font-semibold mb-1.5" style={{color:'var(--body)'}}>산업 · 주거 · 복지</h3>
            <div style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius)'}}>
              {data.context.map((c, i) => (
                <div
                  key={i}
                  className="px-3 py-1.5"
                  style={{
                    borderTop: i === 0 ? 'none' : '1px solid var(--hairline)',
                    borderLeft: c.emphasized ? '3px solid var(--brand)' : '3px solid transparent',
                    background: c.emphasized ? 'var(--canvas)' : 'transparent',
                  }}
                >
                  <div className="flex items-baseline justify-between">
                    <span className="text-sm" style={{color:'var(--body)'}}>
                      {c.emphasized && <span style={{color:'var(--brand)'}} className="mr-1">★</span>}{c.label}
                      <span className="text-xs ml-1" style={{color:'var(--mute)'}}>[{c.axis}]</span>
                    </span>
                    <span className="text-sm font-semibold" style={{color:'var(--ink)'}}>
                      {c.value != null ? `${fmt(c.value)}${c.unit}` : "—"}
                    </span>
                  </div>
                  {c.breakdown?.length > 0 && (
                    <div className="text-xs mt-0.5" style={{color:'var(--mute)'}}>
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
              <h3 className="text-sm font-semibold mb-1.5" style={{color:'var(--body)'}}>파생지표</h3>
              <div className="flex flex-wrap gap-2">
                {data.derived.map((d, i) => (
                  <div
                    key={i}
                    className="px-3 py-2"
                    style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius-sm)'}}
                  >
                    <div className="text-xs" style={{color:'var(--mute)'}}>{d.label}</div>
                    <div className="text-lg font-bold" style={{color:'var(--ink)'}}>
                      {fmt(d.value)}<span className="text-xs font-normal ml-0.5" style={{color:'var(--mute)'}}>{d.unit}</span>
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
