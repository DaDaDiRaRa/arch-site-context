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

export default function TabD() {
  const [addresses, setAddresses] = useState(["", ""]);
  const [useType, setUseType] = useState("주거");
  const [radius, setRadius] = useState(1000);
  const [kinds, setKinds] = useState(["어린이집", "경로당"]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [sort, setSort] = useState(null); // {kind:'fact'|'count', key, dir:1|-1}

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

  // 지표값 추출 (정렬·셀 공용)
  function valueOf(site, kind, key) {
    if (site.error) return null;
    if (kind === "fact") { const f = site.facts.find((x) => x.item === key); return f ? f.value : null; }
    if (kind === "count") return site.counts?.[key] ?? null;
    return null;
  }

  // 정렬 적용된 후보지 순서 (중립 — 선택한 한 지표 기준 재정렬, 종합점수 없음)
  let sites = data ? data.sites : [];
  if (data && sort) {
    sites = [...data.sites].sort((a, b) => {
      const va = valueOf(a, sort.kind, sort.key), vb = valueOf(b, sort.kind, sort.key);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;       // 값 없는 후보지는 뒤로
      if (vb == null) return -1;
      return (va - vb) * sort.dir;
    });
  }
  function sortBy(kind, key) {
    setSort((s) => (s && s.kind === kind && s.key === key ? { kind, key, dir: -s.dir } : { kind, key, dir: -1 }));
  }
  const arrow = (kind, key) => (sort && sort.kind === kind && sort.key === key ? (sort.dir === -1 ? " ▼" : " ▲") : "");

  // 지표 행 목록 (모든 후보지 합집합)
  const factItems = data ? [...new Set(data.sites.flatMap((s) => s.facts.map((f) => f.item)))] : [];
  const natOf = (item) => { for (const s of data.sites) { const f = s.facts.find((x) => x.item === item); if (f && f.national_avg != null) return { v: f.national_avg, u: f.unit }; } return null; };
  const unitOf = (item) => { for (const s of data.sites) { const f = s.facts.find((x) => x.item === item); if (f) return f.unit; } return ""; };
  const diagNames = data ? [...new Set(data.sites.flatMap((s) => s.diagnoses.map((d) => d.name)))] : [];

  const Th = ({ children }) => <th className="text-left px-3 py-2 font-medium text-slate-500 align-bottom">{children}</th>;
  const labelCell = (kind, key, text, suffix = "") => (
    <td className="px-3 py-2 text-slate-700">
      <button onClick={() => sortBy(kind, key)} className="hover:text-blue-700 text-left">
        {text}<span className="text-slate-400">{suffix}</span><span className="text-blue-600">{arrow(kind, key)}</span>
      </button>
    </td>
  );

  return (
    <div>
      <p className="text-sm text-slate-500 mb-4">
        여러 후보지를 한 번에 비교합니다. 지표명을 클릭하면 그 값으로 후보지를 정렬합니다.
        '최고 후보지' 순위는 매기지 않습니다 — 재료만 나란히, <span className="text-amber-700 font-medium">판단은 사람</span>.
      </p>

      {/* 후보지 주소 입력 */}
      <div className="space-y-2">
        {addresses.map((a, i) => (
          <div key={i} className="flex gap-2">
            <input
              value={a}
              onChange={(e) => setAddr(i, e.target.value)}
              placeholder={`후보지 ${i + 1} 주소`}
              className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button onClick={() => delRow(i)} disabled={addresses.length <= 2}
              className="px-3 rounded-lg border border-slate-300 text-slate-400 hover:text-red-600 disabled:opacity-30">×</button>
          </div>
        ))}
        <button onClick={addRow} disabled={addresses.length >= 5}
          className="text-sm text-blue-600 hover:text-blue-800 disabled:opacity-40">+ 후보지 추가 (최대 5)</button>
      </div>

      {/* 옵션 */}
      <div className="flex flex-wrap items-end gap-4 mt-4 text-sm">
        <label>
          <span className="block text-slate-500 mb-1">용도</span>
          <select value={useType} onChange={(e) => setUseType(e.target.value)} className="border border-slate-300 rounded-lg px-3 py-2 bg-white">
            {USE_TYPES.map((u) => <option key={u} value={u}>{u}</option>)}
          </select>
        </label>
        <div>
          <span className="block text-slate-500 mb-1">반경 (m)</span>
          <div className="flex gap-2">
            {RADII_OPTIONS.map((r) => (
              <button key={r} onClick={() => setRadius(r)}
                className={`px-3 py-1.5 rounded-lg border ${radius === r ? "bg-blue-600 border-blue-600 text-white" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"}`}>{r}</button>
            ))}
          </div>
        </div>
      </div>
      <div className="text-sm mt-4">
        <span className="block text-slate-500 mb-1.5">시설 종류</span>
        <div className="flex flex-wrap gap-2">
          {KIND_OPTIONS.map((k) => (
            <button key={k} onClick={() => toggleKind(k)}
              className={`px-3 py-1.5 rounded-full border text-sm ${kinds.includes(k) ? "bg-blue-600 border-blue-600 text-white" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"}`}>{k}</button>
          ))}
        </div>
      </div>

      <button onClick={run} disabled={loading}
        className="mt-5 px-4 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50">후보지 비교</button>

      {loading && <Spinner label="후보지별 통계·시설·수급진단 분석 중…" />}
      <div className="mt-4"><ErrorBox error={error} /></div>

      {data && (
        <div className="mt-5 space-y-6 overflow-x-auto">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="blue">{data.use_type}</Badge>
            <Badge>반경 {data.radius}m</Badge>
            <Badge>기준일 {data.base_date}</Badge>
          </div>

          <table className="w-full text-sm border border-slate-200 rounded-lg">
            <thead className="bg-slate-50">
              <tr>
                <Th>지표</Th>
                {sites.map((s, i) => (
                  <Th key={i}>
                    <div className="text-slate-800 font-semibold">{s.region ? s.region.name : "—"}</div>
                    <div className="text-xs text-slate-400 font-normal max-w-[160px] truncate">{s.address}</div>
                  </Th>
                ))}
                <Th>전국</Th>
              </tr>
            </thead>
            <tbody>
              {/* 지역 통계 (A) */}
              <tr className="bg-slate-50/60"><td colSpan={sites.length + 2} className="px-3 py-1.5 text-xs font-semibold text-slate-500">지역 통계 (시군구 평균)</td></tr>
              {factItems.map((item) => {
                const nat = natOf(item), u = unitOf(item);
                return (
                  <tr key={item} className="border-t border-slate-100">
                    {labelCell("fact", item, item)}
                    {sites.map((s, i) => {
                      const v = valueOf(s, "fact", item);
                      return <td key={i} className="px-3 py-2 text-right font-semibold text-slate-900">{v != null ? `${fmt(v)}${u}` : "—"}</td>;
                    })}
                    <td className="px-3 py-2 text-right text-slate-400">{nat ? `${fmt(nat.v)}${nat.u}` : "—"}</td>
                  </tr>
                );
              })}

              {/* 주변 시설 (B) */}
              <tr className="bg-slate-50/60"><td colSpan={sites.length + 2} className="px-3 py-1.5 text-xs font-semibold text-slate-500">주변 시설 (반경 {data.radius}m 개수)</td></tr>
              {data.kinds.map((k) => (
                <tr key={k} className="border-t border-slate-100">
                  {labelCell("count", k, k)}
                  {sites.map((s, i) => {
                    const v = valueOf(s, "count", k);
                    return <td key={i} className="px-3 py-2 text-right font-semibold text-slate-900">{v != null ? v : "—"}</td>;
                  })}
                  <td className="px-3 py-2"></td>
                </tr>
              ))}

              {/* 수급진단 (P11) */}
              {diagNames.length > 0 && (
                <tr className="bg-slate-50/60"><td colSpan={sites.length + 2} className="px-3 py-1.5 text-xs font-semibold text-slate-500">수급진단 <span className="text-amber-600">참고</span></td></tr>
              )}
              {diagNames.map((name) => (
                <tr key={name} className="border-t border-slate-100">
                  <td className="px-3 py-2 text-slate-700">{name}</td>
                  {sites.map((s, i) => {
                    const d = s.diagnoses.find((x) => x.name === name);
                    return <td key={i} className="px-3 py-2 text-center text-xs text-slate-600">{d ? d.signal : "—"}</td>;
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
                <div key={i} className="text-sm text-amber-700">⚠ {s.address}: {s.error}</div>
              ))}
            </div>
          )}
          {sites.map((s, i) => (s.notes && s.notes.length > 0 ? (
            <details key={i} className="text-xs">
              <summary className="cursor-pointer text-slate-500">{s.region ? s.region.name : s.address} 메모 {s.notes.length}건</summary>
              <Notes notes={s.notes} />
            </details>
          ) : null))}
        </div>
      )}
    </div>
  );
}
