import { useState } from "react";
import { facilities, facilitiesMap } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes } from "./ui.jsx";

const KIND_OPTIONS = ["어린이집", "경로당", "학교", "병원", "약국", "공원", "도서관", "지하철역", "버스정류장", "카페"];
const RADII_OPTIONS = [500, 1000, 2000];

export default function TabB({ address }) {
  const [kinds, setKinds] = useState(["어린이집", "경로당"]);
  const [radii, setRadii] = useState([500, 1000, 2000]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const [mapLoading, setMapLoading] = useState(false);
  const [mapError, setMapError] = useState(null);
  const [map, setMap] = useState(null);

  function toggle(list, setList, v) {
    setList(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  }

  async function run() {
    if (!address.trim()) return setError({ message: "주소를 먼저 입력하세요." });
    if (kinds.length === 0) return setError({ message: "시설 종류를 하나 이상 선택하세요." });
    if (radii.length === 0) return setError({ message: "반경을 하나 이상 선택하세요." });
    setLoading(true); setError(null); setData(null); setMap(null); setMapError(null);
    try {
      setData(await facilities(address, kinds, [...radii].sort((a, b) => a - b)));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  async function makeMap() {
    setMapLoading(true); setMapError(null); setMap(null);
    try {
      setMap(await facilitiesMap(address, kinds, [...radii].sort((a, b) => a - b)));
    } catch (e) {
      setMapError(e);
    } finally {
      setMapLoading(false);
    }
  }

  const bands = data ? Object.keys(data.counts).sort((a, b) => a - b) : [];
  const kindRows = data ? [...new Set(data.results.map((r) => r.kind))] : [];

  return (
    <div>
      {/* 시설 종류 */}
      <div className="text-sm">
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
              onClick={() => toggle(kinds, setKinds, k)}
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

      {/* 반경 */}
      <div className="text-sm mt-4">
        <span
          className="block mb-1.5"
          style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
        >
          반경 (m)
        </span>
        <div className="flex gap-2">
          {RADII_OPTIONS.map((r) => (
            <button
              key={r}
              onClick={() => toggle(radii, setRadii, r)}
              className="px-3 py-1.5 text-sm"
              style={{
                border: radii.includes(r) ? '1px solid var(--brand)' : '1px solid var(--hairline)',
                borderRadius: 'var(--radius-sm)',
                background: radii.includes(r) ? 'var(--brand)' : 'var(--canvas-elevated)',
                color: radii.includes(r) ? '#fff' : 'var(--body)',
              }}
            >
              {r}
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
        주변 시설 검색
      </button>

      {loading && <Spinner label="카카오 반경 검색 중…" />}
      <div className="mt-4"><ErrorBox error={error} /></div>

      {data && (
        <div className="mt-5 space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="blue">{data.center.address}</Badge>
            <Badge>출처 {data.source}</Badge>
            <Badge>기준일 {data.base_date}</Badge>
          </div>

          {/* 개수표 (반경 × 종류) */}
          <div
            className="overflow-x-auto"
            style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius)'}}
          >
            <table className="w-full text-sm">
              <thead style={{background:'var(--canvas)',color:'var(--mute)'}}>
                <tr>
                  <th className="text-left px-3 py-2 font-medium">종류</th>
                  {bands.map((b) => (
                    <th key={b} className="text-right px-3 py-2 font-medium">{b}m</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {kindRows.map((k) => (
                  <tr key={k} style={{borderTop:'1px solid var(--hairline)'}}>
                    <td className="px-3 py-2" style={{color:'var(--body)'}}>{k}</td>
                    {bands.map((b) => (
                      <td key={b} className="px-3 py-2 text-right font-semibold" style={{color:'var(--ink)'}}>
                        {data.counts[b]?.[k] ?? 0}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 목록 */}
          <details
            style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius)'}}
          >
            <summary className="cursor-pointer px-3 py-2 text-sm select-none" style={{color:'var(--body)'}}>
              시설 목록 {data.results.length}건 (거리순)
            </summary>
            <div className="max-h-72 overflow-y-auto" style={{borderTop:'1px solid var(--hairline)'}}>
              <table className="w-full text-sm">
                <tbody>
                  {data.results.map((r, i) => (
                    <tr key={i} style={{borderTop:'1px solid var(--hairline)'}}>
                      <td className="px-3 py-1.5 w-16" style={{color:'var(--mute)'}}>{r.dist_m}m</td>
                      <td className="px-3 py-1.5 w-20" style={{color:'var(--mute)'}}>{r.kind}</td>
                      <td className="px-3 py-1.5" style={{color:'var(--body)'}}>{r.name}</td>
                      <td className="px-3 py-1.5 text-right w-16" style={{color:'var(--mute)'}}>[{r.radius_band}]</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          <Notes notes={data.notes} />

          {/* 위성 PNG */}
          <div>
            <button
              onClick={makeMap}
              disabled={mapLoading}
              className="px-4 py-2 font-medium disabled:opacity-50"
              style={{
                border: '1px solid var(--brand)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--brand)',
                background: 'var(--canvas-elevated)',
              }}
            >
              위성 지도 PNG 생성
            </button>
            {mapLoading && <Spinner label="VWorld 위성 타일 합성 중…" />}
            <div className="mt-3"><ErrorBox error={mapError} /></div>
            {map && (
              <div className="mt-3">
                <img
                  src={map.url}
                  alt="위성 지도"
                  className="w-full max-w-[520px]"
                  style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius)'}}
                />
                <div className="mt-2">
                  <a
                    href={map.url}
                    download
                    className="text-sm px-3 py-1.5"
                    style={{
                      border: '1px solid var(--hairline)',
                      borderRadius: 'var(--radius-sm)',
                      color: 'var(--body)',
                    }}
                  >
                    PNG 다운로드
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
