import { useState } from "react";
import { diagnose } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes, ProximityChip, IndexBar } from "./ui.jsx";
import { useUseTypeCatalog, UseTypeOptions } from "./useTypes.jsx";

const RADII_OPTIONS = [500, 1000, 2000];
const RESOLUTIONS = ["시군구", "읍면동", "반경"];
const RES_LABEL = { 시군구: "시군구(구)", 읍면동: "읍면동(동)", 반경: "반경(집계구)" };

const demandTone = (lv) => (lv === "높음" ? "amber" : lv === "낮음" ? "blue" : "slate");
const supplyTone = (lv) => (lv === "적음" ? "amber" : lv === "많음" ? "green" : "slate");

export default function TabC({ address }) {
  const [radius, setRadius] = useState(1000);
  const [resolution, setResolution] = useState("시군구");
  const [useType, setUseType] = useState("");  // "" = 전체(용도 무관·P13 미적용)
  const useTypeCatalog = useUseTypeCatalog();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  async function run() {
    if (!address.trim()) return setError({ message: "주소를 먼저 입력하세요." });
    setLoading(true);
    setError(null);
    setData(null);
    try {
      setData(await diagnose(address, radius, resolution, useType || null));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <p className="text-sm mb-4" style={{color:'var(--mute)'}}>
        인구 수요(지역 통계)와 주변 시설 공급(반경 내 개수)을 교차해 무엇이 부족/과잉인지
        읽어드립니다. 모두 <span style={{color:'var(--warn)',fontWeight:500}}>참고</span> — 최종 판단은 사람이.
      </p>

      {/* 반경 */}
      <div className="text-sm">
        <span
          className="block mb-1.5"
          style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
        >
          진단 반경 (m)
        </span>
        <div className="flex gap-2">
          {RADII_OPTIONS.map((r) => (
            <button
              key={r}
              onClick={() => setRadius(r)}
              className="px-3 py-1.5 text-sm"
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

      {/* 수요 분석 단위 */}
      <div className="text-sm mt-3">
        <span
          className="block mb-1.5"
          style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
        >
          수요(인구) 단위
        </span>
        <div className="flex gap-2">
          {RESOLUTIONS.map((r) => (
            <button
              key={r}
              onClick={() => setResolution(r)}
              title="읍면동: 인구지표를 행정동 단위로. 반경: 진단 반경 내 실인구(SGIS 집계구 합산)로 수요·공급 동일 반경. 미지원 지표는 시군구 폴백"
              className="px-3 py-1.5 text-sm"
              style={{
                border: resolution === r ? '1px solid var(--brand)' : '1px solid var(--hairline)',
                borderRadius: 'var(--radius-sm)',
                background: resolution === r ? 'var(--brand)' : 'var(--canvas-elevated)',
                color: resolution === r ? '#fff' : 'var(--body)',
              }}
            >
              {RES_LABEL[r]}
            </button>
          ))}
        </div>
      </div>

      {/* 건물 용도 (P13 — 지정 시 관련 수급규칙만 진단) */}
      <div className="text-sm mt-3">
        <span
          className="block mb-1.5"
          style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
        >
          건물 용도 (선택 · 관련 수급규칙만)
        </span>
        <select
          value={useType}
          onChange={(e) => setUseType(e.target.value)}
          className="px-3 py-1.5 text-sm"
          style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius-sm)',background:'var(--canvas-elevated)',color:'var(--body)'}}
        >
          <option value="">전체 (용도 무관)</option>
          <UseTypeOptions catalog={useTypeCatalog} />
        </select>
      </div>

      <button
        onClick={run}
        disabled={loading}
        className="mt-5 px-4 py-2 font-medium disabled:opacity-50"
        style={{background:'var(--brand)',color:'#fff',borderRadius:'var(--radius-sm)'}}
        onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background='var(--brand-hover)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.background='var(--brand)'; }}
      >
        수급진단
      </button>

      {loading && <Spinner label="수요(KOSIS)·공급(카카오) 교차 분석 중…" />}
      <div className="mt-4"><ErrorBox error={error} /></div>

      {data && (
        <div className="mt-5 space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="blue">{data.region.name} 기준</Badge>
            <Badge>반경 {data.radius}m</Badge>
            <Badge>출처 {data.source}</Badge>
            <Badge>기준일 {data.base_date}</Badge>
          </div>

          {/* 진단 카드 목록 */}
          <div className="space-y-3">
            {data.diagnoses.map((d, i) => (
              <div
                key={i}
                className="p-4"
                style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius)'}}
              >
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <h3 className="text-sm font-semibold" style={{color:'var(--body)'}}>{d.name}</h3>
                  <div className="flex items-center gap-1.5">
                    <Badge tone={demandTone(d.demand.level)}>수요 {d.demand.level}</Badge>
                    <Badge tone={supplyTone(d.supply.level)}>공급 {d.supply.level}</Badge>
                    <Badge tone="amber">{d.tag}</Badge>
                  </div>
                </div>

                {/* 원수치 노출 */}
                <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
                  <div style={{color:'var(--body)'}}>
                    <span className="text-xs flex items-center gap-1.5 flex-wrap" style={{color:'var(--mute)'}}>
                      <span>
                        수요 · {d.demand.source_tbl} {d.demand.year}
                        {d.demand.scope && (
                          <span style={{color: d.demand.scope_level === "읍면동" || d.demand.scope_level === "반경" ? 'var(--ok)' : 'var(--mute)'}}>
                            {" · "}{d.demand.scope} 기준
                          </span>
                        )}
                      </span>
                      <ProximityChip level={d.demand.proximity} />
                    </span>
                    {d.demand.item}{" "}
                    <span className="font-semibold" style={{color:'var(--ink)'}}>{d.demand.value}{d.demand.unit}</span>
                    {d.demand.national_avg != null && (
                      <span style={{color:'var(--mute)'}}> (전국 {d.demand.national_avg}{d.demand.unit})</span>
                    )}
                    {d.demand.index != null && (
                      <span className="flex items-center gap-1.5 mt-0.5">
                        <IndexBar index={d.demand.index} />
                        <span className="text-xs" style={{color:'var(--mute)'}}>전국={"100"} · {d.demand.index_band}</span>
                      </span>
                    )}
                  </div>
                  <div style={{color:'var(--body)'}}>
                    <span className="text-xs flex items-center gap-1.5 flex-wrap" style={{color:'var(--mute)'}}>
                      <span>공급 · 반경 {d.supply.radius}m</span>
                      <ProximityChip level={d.supply.proximity} />
                    </span>
                    {d.supply.kinds.join("·")}{" "}
                    <span className="font-semibold" style={{color:'var(--ink)'}}>{d.supply.count}개</span>
                    {d.supply.capacity != null && (
                      <span style={{color:'var(--body)'}}>
                        {" · "}정원{" "}
                        <span className="font-semibold" style={{color:'var(--ink)'}}>
                          {d.supply.capacity.toLocaleString("ko-KR")}명
                        </span>
                        {d.supply.capacity_scope && (
                          <span style={{color:'var(--mute)'}}> ({d.supply.capacity_scope})</span>
                        )}
                      </span>
                    )}
                    {d.supply.workforce != null && (
                      <span style={{color:'var(--body)'}}>
                        {" · "}의료인력{" "}
                        <span className="font-semibold" style={{color:'var(--ink)'}}>
                          {d.supply.workforce.toLocaleString("ko-KR")}명
                        </span>
                        {d.supply.workforce_per_10k != null && (
                          <span style={{color:'var(--mute)'}}> ({d.supply.workforce_per_10k}/만명·{d.supply.workforce_scope})</span>
                        )}
                      </span>
                    )}
                    {d.supply.vs_national_pct != null && (
                      <span className="block text-xs mt-0.5" style={{color:'var(--mute)'}}>
                        {d.supply.density_per_10k}개/만명 · 전국{" "}
                        {d.supply.national_density_per_10k}개/만명 대비{" "}
                        <span style={{color: d.supply.vs_national_pct < 100 ? 'var(--warn)' : 'var(--ok)'}}>
                          {d.supply.vs_national_pct}%
                        </span>
                        <span style={{color:'var(--hairline)'}}>
                          {d.supply.density_basis === "반경"
                            ? " (반경 실인구 1만명당 · 공급판정 기준)"
                            : " (참고·시군구 인구 기준)"}
                        </span>
                      </span>
                    )}
                  </div>
                </div>

                <p
                  className="mt-3 text-sm px-3 py-2"
                  style={{
                    background:'var(--canvas-elevated)',
                    border:'1px solid var(--hairline)',
                    borderRadius:'var(--radius-sm)',
                    color:'var(--body)',
                  }}
                >
                  {d.note}
                </p>
              </div>
            ))}
          </div>

          <Notes notes={data.notes} />
        </div>
      )}
    </div>
  );
}
