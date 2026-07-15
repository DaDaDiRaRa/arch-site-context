import { useState } from "react";
import { ask } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes, CopyButton } from "./ui.jsx";

import { useUseTypeCatalog, UseTypeOptions, DEFAULT_USE_TYPE } from "./useTypes";
const KIND_OPTIONS = ["어린이집", "경로당", "학교", "병원", "약국", "공원", "도서관", "지하철역", "버스정류장", "카페"];
const RADII_OPTIONS = [500, 1000, 2000];

function fmt(v) {
  if (typeof v === "number" && Number.isInteger(v) && Math.abs(v) >= 1000) return v.toLocaleString("ko-KR");
  return v;
}

const selStyle = {
  border: '1px solid var(--hairline)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--ink)',
  background: 'var(--canvas-elevated)',
};

export default function TabE({ address }) {
  const [useType, setUseType] = useState(DEFAULT_USE_TYPE);
  const useTypeCatalog = useUseTypeCatalog();
  const [radius, setRadius] = useState(1000);
  const [kinds, setKinds] = useState(["어린이집", "경로당"]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [webLoading, setWebLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [textareaFocused, setTextareaFocused] = useState(false);

  function toggleKind(k) { setKinds(kinds.includes(k) ? kinds.filter((x) => x !== k) : [...kinds, k]); }

  async function run(web = false) {
    if (!address.trim()) return setError({ message: "주소를 먼저 입력하세요." });
    if (!question.trim()) return setError({ message: "질문을 입력하세요." });
    web ? setWebLoading(true) : setLoading(true);
    setError(null);
    if (!web) setData(null);
    try {
      const res = await ask(address, question, useType, radius, kinds, web);
      setData(res);
    } catch (e) {
      setError(e);
    } finally {
      web ? setWebLoading(false) : setLoading(false);
    }
  }

  const isWeb = data && data.source === "ai_web";

  return (
    <div>
      <p className="text-sm mb-4" style={{color:'var(--mute)'}}>
        이 주소의 데이터(지역통계·주변시설·수급진단) <span className="font-medium" style={{color:'var(--ink)'}}>위에서만</span> 답합니다.
        데이터로 답할 수 없으면 <span style={{color:'var(--warn)',fontWeight:500}}>확인 불가</span>로 멈춥니다 — 추정하지 않습니다.
      </p>

      {/* 옵션 */}
      <div className="flex flex-wrap items-end gap-4 text-sm">
        <label>
          <span
            className="block mb-1"
            style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
          >
            용도
          </span>
          <select value={useType} onChange={(e) => setUseType(e.target.value)} className="px-3 py-2" style={selStyle}>
            <UseTypeOptions catalog={useTypeCatalog} />
          </select>
        </label>
        <div>
          <span
            className="block mb-1"
            style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
          >
            반경 (m)
          </span>
          <div className="flex gap-2">
            {RADII_OPTIONS.map((r) => (
              <button
                key={r}
                onClick={() => setRadius(r)}
                className="px-3 py-1.5"
                style={{
                  border: radius === r ? '1px solid var(--brand)' : '1px solid var(--hairline)',
                  borderRadius: 'var(--radius-sm)',
                  background: radius === r ? 'var(--brand)' : 'var(--canvas-elevated)',
                  color: radius === r ? '#fff' : 'var(--body)',
                }}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="text-sm mt-4">
        <span
          className="block mb-1.5"
          style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
        >
          시설 종류 (답변 근거에 포함)
        </span>
        <div className="flex flex-wrap gap-2">
          {KIND_OPTIONS.map((k) => (
            <button
              key={k}
              onClick={() => toggleKind(k)}
              className="px-3 py-1.5 text-sm"
              style={{
                border: kinds.includes(k) ? '1px solid var(--brand)' : '1px solid var(--hairline)',
                borderRadius: 'var(--radius-sm)',
                background: kinds.includes(k) ? 'var(--brand)' : 'var(--canvas-elevated)',
                color: kinds.includes(k) ? '#fff' : 'var(--body)',
              }}
            >
              {k}
            </button>
          ))}
        </div>
      </div>

      {/* 질문 */}
      <div className="mt-4">
        <label
          className="block mb-1"
          style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
        >
          질문
        </label>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={2}
          placeholder="예) 고령인구 비율이 전국보다 높아? 반경 내 어린이집은 몇 개야?"
          className="w-full px-3 py-2 text-sm focus:outline-none"
          style={{
            border: `1px solid ${textareaFocused ? 'var(--brand)' : 'var(--hairline)'}`,
            borderRadius: 'var(--radius-sm)',
            color: 'var(--ink)',
            background: 'var(--canvas-elevated)',
          }}
          onFocus={() => setTextareaFocused(true)}
          onBlur={() => setTextareaFocused(false)}
        />
      </div>

      <button
        onClick={() => run(false)}
        disabled={loading || webLoading}
        className="mt-3 px-4 py-2 font-medium disabled:opacity-50"
        style={{background:'var(--brand)',color:'#fff',borderRadius:'var(--radius-sm)'}}
        onMouseEnter={(e) => { if (!loading && !webLoading) e.currentTarget.style.background='var(--brand-hover)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.background='var(--brand)'; }}
      >
        물어보기
      </button>

      {loading && <Spinner label="데이터 위에서 답 찾는 중…" />}
      <div className="mt-4"><ErrorBox error={error} /></div>

      {data && (
        <div className="mt-5 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {data.region && <Badge tone="blue">{data.region.name} 기준</Badge>}
            <Badge tone={isWeb ? "amber" : (data.answerable ? "green" : "amber")}>
              {isWeb ? "외부·웹검색 참고" : (data.answerable ? "데이터 기반" : "확인 불가")}
            </Badge>
          </div>

          {/* 답변 */}
          <div
            className="p-4"
            style={{
              border: isWeb ? '1px solid var(--warn)' : '1px solid var(--hairline)',
              borderLeft: isWeb ? '3px solid var(--warn)' : '1px solid var(--hairline)',
              borderRadius: 'var(--radius)',
              background: 'var(--canvas-elevated)',
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold" style={{color:'var(--body)'}}>{isWeb ? "웹검색 답변 (참고)" : "답변"}</h3>
              <CopyButton text={data.answer} />
            </div>
            <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{color:'var(--body)'}}>{data.answer}</p>

            {/* 웹 출처 */}
            {isWeb && data.web_sources?.length > 0 && (
              <ul className="mt-3 text-xs space-y-1">
                {data.web_sources.map((s, i) => (
                  <li key={i}>
                    <a href={s.url} target="_blank" rel="noreferrer" style={{color:'var(--brand)'}} className="hover:underline">
                      {s.title || s.url}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* 데이터 밖 → 웹 폴백 (opt-in) */}
          {!data.answerable && !isWeb && (
            <div>
              <button
                onClick={() => run(true)}
                disabled={webLoading}
                className="px-4 py-2 font-medium disabled:opacity-50"
                style={{
                  border: '1px solid var(--warn)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--warn)',
                  background: 'var(--canvas-elevated)',
                }}
              >
                웹에서 찾아보기 (외부·참고)
              </button>
              {webLoading && <Spinner label="웹검색 중…" />}
            </div>
          )}

          {/* 근거 데이터 (투명성) */}
          <details style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius)'}}>
            <summary className="cursor-pointer px-3 py-2 text-sm select-none" style={{color:'var(--body)'}}>
              답변이 근거한 데이터 보기 (지역통계 {data.facts.length} · 시설 {Object.keys(data.counts).length}종 · 수급진단 {data.diagnoses.length})
            </summary>
            <div className="px-3 py-3 space-y-3 text-sm" style={{borderTop:'1px solid var(--hairline)'}}>
              {data.facts.length > 0 && (
                <div>
                  <div className="text-xs mb-1" style={{color:'var(--mute)'}}>지역 통계 (시군구 평균)</div>
                  {data.facts.map((f, i) => (
                    <div key={i} style={{color:'var(--body)'}}>{f.item}: <b>{fmt(f.value)}{f.unit}</b>
                      {f.national_avg != null && <span style={{color:'var(--mute)'}}> (전국 {fmt(f.national_avg)}{f.unit})</span>}
                      <span className="text-xs" style={{color:'var(--hairline)'}}> · {f.source_tbl} {f.year}</span>
                    </div>
                  ))}
                </div>
              )}
              <div>
                <div className="text-xs mb-1" style={{color:'var(--mute)'}}>반경 {data.radius}m 시설</div>
                <div style={{color:'var(--body)'}}>{Object.entries(data.counts).map(([k, v]) => `${k} ${v}개`).join(" · ") || "—"}</div>
              </div>
              {data.diagnoses.length > 0 && (
                <div>
                  <div className="text-xs mb-1" style={{color:'var(--mute)'}}>수급진단 (참고)</div>
                  {data.diagnoses.map((d, i) => <div key={i} style={{color:'var(--body)'}}>{d.name}: {d.signal}</div>)}
                </div>
              )}
            </div>
          </details>

          <Notes notes={data.notes} />
        </div>
      )}
    </div>
  );
}
