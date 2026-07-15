import { useState, Fragment } from "react";
import { analyze } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes, CopyButton, ProximityChip, IndexBar } from "./ui.jsx";

import { useUseTypeCatalog, UseTypeOptions, DEFAULT_USE_TYPE } from "./useTypes";

function fmt(v) {
  if (typeof v === "number" && Number.isInteger(v) && Math.abs(v) >= 1000) {
    return v.toLocaleString("ko-KR");
  }
  return v;
}

const RESOLUTIONS = ["시군구", "읍면동", "반경"];
const RES_LABEL = { 시군구: "시군구(구)", 읍면동: "읍면동(동)", 반경: "반경(집계구)" };
const RADII = [500, 1000, 2000];

const selStyle = {
  border: '1px solid var(--hairline)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--ink)',
  background: 'var(--canvas-elevated)',
};

function ToggleBtn({ active, onClick, children, title }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="px-3 py-1.5 text-sm"
      style={{
        border: active ? '1px solid var(--brand)' : '1px solid var(--hairline)',
        borderRadius: 'var(--radius-sm)',
        background: active ? 'var(--brand)' : 'var(--canvas-elevated)',
        color: active ? '#fff' : 'var(--body)',
      }}
    >
      {children}
    </button>
  );
}

export default function TabA({ address }) {
  const [useType, setUseType] = useState(DEFAULT_USE_TYPE);
  const useTypeCatalog = useUseTypeCatalog();
  const [resolution, setResolution] = useState("시군구");
  const [radius, setRadius] = useState(1000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [open, setOpen] = useState({});  // T1 근거 드릴다운 (fact index → 열림 여부)

  async function run() {
    if (!address.trim()) {
      setError({ message: "주소를 먼저 입력하세요." });
      return;
    }
    setLoading(true);
    setError(null);
    setData(null);
    try {
      setData(await analyze(address, useType, null, resolution, radius));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span
            className="block mb-1"
            style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
          >
            건물 용도
          </span>
          <select
            value={useType}
            onChange={(e) => setUseType(e.target.value)}
            className="px-3 py-2"
            style={selStyle}
          >
            <UseTypeOptions catalog={useTypeCatalog} />
          </select>
        </label>
        <label className="text-sm">
          <span
            className="block mb-1"
            style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
          >
            분석 단위
          </span>
          <select
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            className="px-3 py-2"
            style={selStyle}
            title="읍면동: 인구·연령을 행정동 단위로. 반경: 반경 내 실인구(SGIS 집계구 합산). 미지원 지표는 시군구 폴백"
          >
            {RESOLUTIONS.map((r) => (
              <option key={r} value={r}>{RES_LABEL[r]}</option>
            ))}
          </select>
        </label>
        {resolution === "반경" && (
          <label className="text-sm">
            <span
              className="block mb-1"
              style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
            >
              반경 (m)
            </span>
            <select
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              className="px-3 py-2"
              style={selStyle}
            >
              {RADII.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </label>
        )}
        <button
          onClick={run}
          disabled={loading}
          className="px-4 py-2 font-medium disabled:opacity-50"
          style={{background:'var(--brand)',color:'#fff',borderRadius:'var(--radius-sm)'}}
          onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background='var(--brand-hover)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background='var(--brand)'; }}
        >
          지역 통계 분석
        </button>
      </div>

      {loading && <Spinner label="KOSIS 통계 조회 중…" />}
      <div className="mt-4">
        <ErrorBox error={error} />
      </div>

      {data && (
        <div className="mt-5 space-y-5">
          {/* 지역·연도·출처 배지 */}
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="blue">{data.region.name} 기준</Badge>
            <Badge>{data.region.resolution}</Badge>
            <Badge>{data.year}년</Badge>
            <Badge tone={data.source === "ai" ? "green" : "amber"}>
              {data.source === "ai" ? "AI 서술" : "규칙 기반"}
            </Badge>
          </div>

          {/* facts 표 */}
          <div
            className="overflow-x-auto"
            style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius)'}}
          >
            <table className="w-full text-sm">
              <thead style={{background:'var(--canvas)',color:'var(--mute)'}}>
                <tr>
                  <th className="text-left px-3 py-2 font-medium">항목</th>
                  <th className="text-right px-3 py-2 font-medium">값</th>
                  <th className="text-right px-3 py-2 font-medium">전국 평균</th>
                  <th className="text-left px-3 py-2 font-medium">전국 대비 (100)</th>
                  <th className="text-left px-3 py-2 font-medium">기준 지역 · 근접도</th>
                  <th className="text-left px-3 py-2 font-medium">출처 · 연도</th>
                </tr>
              </thead>
              <tbody>
                {data.facts.map((f, i) => (
                  <Fragment key={i}>
                    <tr
                      onClick={() => setOpen((o) => ({ ...o, [i]: !o[i] }))}
                      style={{ borderTop: '1px solid var(--hairline)', cursor: 'pointer' }}
                      title="클릭 → 근거 보기"
                    >
                      <td className="px-3 py-2" style={{color:'var(--body)'}}>
                        <span style={{color:'var(--mute)',fontSize:10,marginRight:4}}>{open[i] ? "▾" : "▸"}</span>
                        {f.item}
                      </td>
                      <td className="px-3 py-2 text-right font-semibold" style={{color:'var(--ink)'}}>
                        {fmt(f.value)}{f.unit}
                      </td>
                      <td className="px-3 py-2 text-right" style={{color:'var(--mute)'}}>
                        {f.national_avg != null ? fmt(f.national_avg) : "—"}{f.national_avg != null ? f.unit : ""}
                      </td>
                      <td className="px-3 py-2"><IndexBar index={f.index} /></td>
                      <td className="px-3 py-2">
                        <span className="inline-flex items-center gap-1.5">
                          {f.scope ? (
                            <Badge tone="slate">{f.scope}</Badge>
                          ) : (
                            <span style={{color:'var(--hairline)'}}>—</span>
                          )}
                          <ProximityChip level={f.proximity} />
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs" style={{color:'var(--mute)'}}>
                        {f.source_tbl} · {f.year}
                      </td>
                    </tr>
                    {open[i] && (
                      <tr style={{ background: 'var(--canvas)' }}>
                        <td colSpan={6} className="px-3 py-2 text-xs" style={{ color: 'var(--body)' }}>
                          <span style={{ color: 'var(--mute)' }}>근거 · </span>
                          {f.item} <b>{fmt(f.value)}{f.unit}</b>
                          {f.national_avg != null && <> (전국 {fmt(f.national_avg)}{f.unit}{f.index != null && <> · 지수 <b>{f.index}</b> {f.index_band}</>})</>}
                          {" · "}기준 지역 <b>{f.scope || "—"}</b> (근접도 {f.proximity || "—"})
                          {" · "}출처 <b>{f.source_tbl}</b> · {f.year}
                          {f.source_type && <> · {f.source_type}</>}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>

          {/* 시사점 */}
          {data.implications.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold mb-2" style={{color:'var(--body)'}}>참고 시사점</h3>
              <ul className="space-y-1.5">
                {data.implications.map((im, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm" style={{color:'var(--body)'}}>
                    <Badge tone="amber">{im.tag}</Badge>
                    <span>{im.text}<span style={{color:'var(--mute)'}}> · {im.basis}</span></span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 한 문단 */}
          <div
            className="p-4"
            style={{
              border:'1px solid var(--hairline)',
              borderRadius:'var(--radius)',
              background:'var(--canvas-elevated)',
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold" style={{color:'var(--body)'}}>초안 문단</h3>
              <CopyButton text={data.draft_paragraph} />
            </div>
            <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{color:'var(--body)'}}>
              {data.draft_paragraph}
            </p>
          </div>

          <Notes notes={data.notes} />
        </div>
      )}
    </div>
  );
}
