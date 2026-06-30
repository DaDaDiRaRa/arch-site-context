import { useState } from "react";
import { diagnose } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes } from "./ui.jsx";

const RADII_OPTIONS = [500, 1000, 2000];
const RESOLUTIONS = ["시군구", "읍면동", "반경"];
const RES_LABEL = { 시군구: "시군구(구)", 읍면동: "읍면동(동)", 반경: "반경(집계구)" };

// 수요/공급 레벨에 따른 배지 색. 좋다/나쁘다 단정이 아니라 신호 강약 표시일 뿐.
const demandTone = (lv) => (lv === "높음" ? "amber" : lv === "낮음" ? "blue" : "slate");
const supplyTone = (lv) => (lv === "적음" ? "amber" : lv === "많음" ? "green" : "slate");

export default function TabC({ address }) {
  const [radius, setRadius] = useState(1000);
  const [resolution, setResolution] = useState("시군구");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  async function run() {
    if (!address.trim()) return setError({ message: "주소를 먼저 입력하세요." });
    setLoading(true);
    setError(null);
    setData(null);
    try {
      setData(await diagnose(address, radius, resolution));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <p className="text-sm text-slate-500 mb-4">
        인구 수요(지역 통계)와 주변 시설 공급(반경 내 개수)을 교차해 무엇이 부족/과잉인지
        읽어드립니다. 모두 <span className="text-amber-700 font-medium">참고</span> — 최종 판단은 사람이.
      </p>

      {/* 반경 */}
      <div className="text-sm">
        <span className="block text-slate-500 mb-1.5">진단 반경 (m)</span>
        <div className="flex gap-2">
          {RADII_OPTIONS.map((r) => (
            <button
              key={r}
              onClick={() => setRadius(r)}
              className={`px-3 py-1.5 rounded-lg border text-sm ${radius === r ? "bg-blue-600 border-blue-600 text-white" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"}`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* 수요 분석 단위 */}
      <div className="text-sm mt-3">
        <span className="block text-slate-500 mb-1.5">수요(인구) 단위</span>
        <div className="flex gap-2">
          {RESOLUTIONS.map((r) => (
            <button
              key={r}
              onClick={() => setResolution(r)}
              title="읍면동: 인구지표를 행정동 단위로. 반경: 진단 반경 내 실인구(SGIS 집계구 합산)로 수요·공급 동일 반경. 미지원 지표는 시군구 폴백"
              className={`px-3 py-1.5 rounded-lg border text-sm ${resolution === r ? "bg-blue-600 border-blue-600 text-white" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"}`}
            >
              {RES_LABEL[r]}
            </button>
          ))}
        </div>
      </div>

      <button
        onClick={run}
        disabled={loading}
        className="mt-5 px-4 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50"
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
              <div key={i} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <h3 className="text-sm font-semibold text-slate-800">{d.name}</h3>
                  <div className="flex items-center gap-1.5">
                    <Badge tone={demandTone(d.demand.level)}>수요 {d.demand.level}</Badge>
                    <Badge tone={supplyTone(d.supply.level)}>공급 {d.supply.level}</Badge>
                    <Badge tone="amber">{d.tag}</Badge>
                  </div>
                </div>

                {/* 원수치 노출 (절대 원칙: 재료·근거 제시) */}
                <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
                  <div className="text-slate-600">
                    <span className="text-slate-400 text-xs block">
                      수요 · {d.demand.source_tbl} {d.demand.year}
                      {d.demand.scope && (
                        <span className={d.demand.scope_level === "읍면동" || d.demand.scope_level === "반경" ? "text-emerald-600" : "text-slate-400"}>
                          {" · "}{d.demand.scope} 기준
                        </span>
                      )}
                    </span>
                    {d.demand.item}{" "}
                    <span className="font-semibold text-slate-900">{d.demand.value}{d.demand.unit}</span>
                    {d.demand.national_avg != null && (
                      <span className="text-slate-400"> (전국 {d.demand.national_avg}{d.demand.unit})</span>
                    )}
                  </div>
                  <div className="text-slate-600">
                    <span className="text-slate-400 text-xs block">공급 · 반경 {d.supply.radius}m</span>
                    {d.supply.kinds.join("·")}{" "}
                    <span className="font-semibold text-slate-900">{d.supply.count}개</span>
                    {/* 시군구 정원(어린이집 등) — 반경 개수와 단위 다름, 참고 */}
                    {d.supply.capacity != null && (
                      <span className="text-slate-500">
                        {" · "}정원{" "}
                        <span className="font-semibold text-slate-700">
                          {d.supply.capacity.toLocaleString("ko-KR")}명
                        </span>
                        {d.supply.capacity_scope && (
                          <span className="text-slate-400"> ({d.supply.capacity_scope})</span>
                        )}
                      </span>
                    )}
                    {/* 전국 대비 밀도 — 분모 시군구 전체인구, 참고용 */}
                    {d.supply.vs_national_pct != null && (
                      <span className="block text-xs text-slate-400 mt-0.5">
                        {d.supply.density_per_10k}개/만명 · 전국{" "}
                        {d.supply.national_density_per_10k}개/만명 대비{" "}
                        <span className={d.supply.vs_national_pct < 100 ? "text-amber-600" : "text-emerald-600"}>
                          {d.supply.vs_national_pct}%
                        </span>
                        <span className="text-slate-300">
                          {d.supply.density_basis === "반경"
                            ? " (반경 실인구 1만명당 · 공급판정 기준)"
                            : " (참고·시군구 인구 기준)"}
                        </span>
                      </span>
                    )}
                  </div>
                </div>

                <p className="mt-3 text-sm text-slate-700 bg-slate-50 rounded-md px-3 py-2">
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
