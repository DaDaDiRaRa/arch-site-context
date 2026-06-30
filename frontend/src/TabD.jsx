import { useState } from "react";
import { compare } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes } from "./ui.jsx";

const USE_TYPES = ["주거", "상업", "의료"];
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

const inputStyle = {
  border: '1px solid var(--hairline)',
  borderRadius: 'var(--radius-sm)',
  fontSize: 14,
  color: 'var(--ink)',
  background: 'var(--canvas-elevated)',
};

export default function TabD() {
  const [addresses, setAddresses] = useState(["", ""]);
  const [useType, setUseType] = useState("주거");
  const [radius, setRadius] = useState(1000);
  const [kinds, setKinds] = useState(["어린이집", "경로당"]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [sort, setSort] = useState(null);

  function setAddr(i, v) { setAddresses(addresses.map((a, idx) => (idx === i ? v : a))); }
  function addRow() { if (addresses.length < 5) setAddresses([...addresses, ""]); }
  function delRow(i) { if (addresses.length > 2) setAddresses(addresses.filter((_, idx) => idx !== i)); }
  function toggleKind(k) { setKinds(kinds.includes(k) ? kinds.filter((x) => x !== k) : [...kinds, k]); }

  async function run() {
    const addrs = addresses.map((a) => a.trim()).filter(Boolean);
    if (addrs.length < 2) return setError({ message: "후보지 주소를 2개 이상 입력하세요." });
    setLoading(true); setError(null); setData(null); setSort(null);
    try {
      setData(await compare(addrs, useType, radius, kinds));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  function valueOf(site, kind, key) {
    if (site.error) return null;
    if (kind === "fact") { const f = site.facts.find((x) => x.item === key); return f ? f.value : null; }
    if (kind === "count") return site.counts?.[key] ?? null;
    return null;
  }

  let sites = data ? data.sites : [];
  if (data && sort) {
    sites = [...data.sites].sort((a, b) => {
      const va = valueOf(a, sort.kind, sort.key), vb = valueOf(b, sort.kind, sort.key);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      return (va - vb) * sort.dir;
    });
  }
  function sortBy(kind, key) {
    setSort((s) => (s && s.kind === kind && s.key === key ? { kind, key, dir: -s.dir } : { kind, key, dir: -1 }));
  }
  const arrow = (kind, key) => (sort && sort.kind === kind && sort.key === key ? (sort.dir === -1 ? " ▼" : " ▲") : "");

  const factItems = data ? [...new Set(data.sites.flatMap((s) => s.facts.map((f) => f.item)))] : [];
  const natOf = (item) => { for (const s of data.sites) { const f = s.facts.find((x) => x.item === item); if (f && f.national_avg != null) return { v: f.national_avg, u: f.unit }; } return null; };
  const unitOf = (item) => { for (const s of data.sites) { const f = s.facts.find((x) => x.item === item); if (f) return f.unit; } return ""; };
  const diagNames = data ? [...new Set(data.sites.flatMap((s) => s.diagnoses.map((d) => d.name)))] : [];

  const Th = ({ children }) => (
    <th className="text-left px-3 py-2 font-medium align-bottom" style={{color:'var(--mute)'}}>{children}</th>
  );
  const labelCell = (kind, key, text, suffix = "") => (
    <td className="px-3 py-2" style={{color:'var(--body)'}}>
      <button onClick={() => sortBy(kind, key)} className="text-left hover:underline">
        {text}<span style={{color:'var(--mute)'}}>{suffix}</span>
        <span style={{color:'var(--brand)'}}>{arrow(kind, key)}</span>
      </button>
    </td>
  );

  return (
    <div>
      <p className="text-sm mb-4" style={{color:'var(--mute)'}}>
        여러 후보지를 한 번에 비교합니다. 지표명을 클릭하면 그 값으로 후보지를 정렬합니다.
        '최고 후보지' 순위는 매기지 않습니다 — 재료만 나란히,{" "}
        <span style={{color:'var(--warn)',fontWeight:500}}>판단은 사람</span>.
      </p>

      {/* 후보지 주소 입력 */}
      <div className="space-y-2">
        {addresses.map((a, i) => (
          <div key={i} className="flex gap-2">
            <input
              value={a}
              onChange={(e) => setAddr(i, e.target.value)}
              placeholder={`후보지 ${i + 1} 주소`}
              className="flex-1 px-3 py-2 text-sm focus:outline-none"
              style={inputStyle}
            />
            <button
              onClick={() => delRow(i)}
              disabled={addresses.length <= 2}
              className="px-3 disabled:opacity-30"
              style={{
                border: '1px solid var(--hairline)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--mute)',
              }}
            >
              ×
            </button>
          </div>
        ))}
        <button
          onClick={addRow}
          disabled={addresses.length >= 5}
          className="text-sm disabled:opacity-40"
          style={{color:'var(--brand)'}}
        >
          + 후보지 추가 (최대 5)
        </button>
      </div>

      {/* 옵션 */}
      <div className="flex flex-wrap items-end gap-4 mt-4 text-sm">
        <label>
          <span
            className="block mb-1"
            style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
          >
            용도
          </span>
          <select value={useType} onChange={(e) => setUseType(e.target.value)} className="px-3 py-2" style={selStyle}>
            {USE_TYPES.map((u) => <option key={u} value={u}>{u}</option>)}
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
          시설 종류
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

      <button
        onClick={run}
        disabled={loading}
        className="mt-5 px-4 py-2 font-medium disabled:opacity-50"
        style={{background:'var(--brand)',color:'#fff',borderRadius:'var(--radius-sm)'}}
        onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background='var(--brand-hover)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.background='var(--brand)'; }}
      >
        후보지 비교
      </button>

      {loading && <Spinner label="후보지별 통계·시설·수급진단 분석 중…" />}
      <div className="mt-4"><ErrorBox error={error} /></div>

      {data && (
        <div className="mt-5 space-y-6 overflow-x-auto">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="blue">{data.use_type}</Badge>
            <Badge>반경 {data.radius}m</Badge>
            <Badge>기준일 {data.base_date}</Badge>
          </div>

          <table
            className="w-full text-sm"
            style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius)'}}
          >
            <thead style={{background:'var(--canvas)'}}>
              <tr>
                <Th>지표</Th>
                {sites.map((s, i) => (
                  <Th key={i}>
                    <div className="font-semibold" style={{color:'var(--body)'}}>{s.region ? s.region.name : "—"}</div>
                    <div className="text-xs font-normal max-w-[160px] truncate" style={{color:'var(--mute)'}}>{s.address}</div>
                  </Th>
                ))}
                <Th>전국</Th>
              </tr>
            </thead>
            <tbody>
              {/* 지역 통계 (A) */}
              <tr style={{background:'var(--canvas)'}}>
                <td colSpan={sites.length + 2} className="px-3 py-1.5 text-xs font-semibold" style={{color:'var(--mute)'}}>
                  지역 통계 (시군구 평균)
                </td>
              </tr>
              {factItems.map((item) => {
                const nat = natOf(item), u = unitOf(item);
                return (
                  <tr key={item} style={{borderTop:'1px solid var(--hairline)'}}>
                    {labelCell("fact", item, item)}
                    {sites.map((s, i) => {
                      const v = valueOf(s, "fact", item);
                      return <td key={i} className="px-3 py-2 text-right font-semibold" style={{color:'var(--ink)'}}>{v != null ? `${fmt(v)}${u}` : "—"}</td>;
                    })}
                    <td className="px-3 py-2 text-right" style={{color:'var(--mute)'}}>{nat ? `${fmt(nat.v)}${nat.u}` : "—"}</td>
                  </tr>
                );
              })}

              {/* 주변 시설 (B) */}
              <tr style={{background:'var(--canvas)'}}>
                <td colSpan={sites.length + 2} className="px-3 py-1.5 text-xs font-semibold" style={{color:'var(--mute)'}}>
                  주변 시설 (반경 {data.radius}m 개수)
                </td>
              </tr>
              {data.kinds.map((k) => (
                <tr key={k} style={{borderTop:'1px solid var(--hairline)'}}>
                  {labelCell("count", k, k)}
                  {sites.map((s, i) => {
                    const v = valueOf(s, "count", k);
                    return <td key={i} className="px-3 py-2 text-right font-semibold" style={{color:'var(--ink)'}}>{v != null ? v : "—"}</td>;
                  })}
                  <td className="px-3 py-2"></td>
                </tr>
              ))}

              {/* 수급진단 (P11) */}
              {diagNames.length > 0 && (
                <tr style={{background:'var(--canvas)'}}>
                  <td colSpan={sites.length + 2} className="px-3 py-1.5 text-xs font-semibold" style={{color:'var(--mute)'}}>
                    수급진단 <span style={{color:'var(--warn)'}}>참고</span>
                  </td>
                </tr>
              )}
              {diagNames.map((name) => (
                <tr key={name} style={{borderTop:'1px solid var(--hairline)'}}>
                  <td className="px-3 py-2" style={{color:'var(--body)'}}>{name}</td>
                  {sites.map((s, i) => {
                    const d = s.diagnoses.find((x) => x.name === name);
                    return <td key={i} className="px-3 py-2 text-center text-xs" style={{color:'var(--body)'}}>{d ? d.signal : "—"}</td>;
                  })}
                  <td className="px-3 py-2"></td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* 후보지별 오류·메모 */}
          {sites.some((s) => s.error) && (
            <div className="space-y-1">
              {sites.filter((s) => s.error).map((s, i) => (
                <div key={i} className="text-sm" style={{color:'var(--warn)'}}>⚠ {s.address}: {s.error}</div>
              ))}
            </div>
          )}
          {sites.map((s, i) => (s.notes && s.notes.length > 0 ? (
            <details key={i} className="text-xs">
              <summary className="cursor-pointer" style={{color:'var(--mute)'}}>{s.region ? s.region.name : s.address} 메모 {s.notes.length}건</summary>
              <Notes notes={s.notes} />
            </details>
          ) : null))}
        </div>
      )}
    </div>
  );
}
