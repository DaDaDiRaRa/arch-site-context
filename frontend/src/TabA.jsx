import { useState } from "react";
import { analyze } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes, CopyButton } from "./ui.jsx";

const USE_TYPES = ["주거", "상업", "의료"];

// 큰 정수는 천단위 구분 (예: 371362 → 371,362). 비율 등 소수는 그대로.
function fmt(v) {
  if (typeof v === "number" && Number.isInteger(v) && Math.abs(v) >= 1000) {
    return v.toLocaleString("ko-KR");
  }
  return v;
}

export default function TabA({ address }) {
  const [useType, setUseType] = useState("주거");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  async function run() {
    if (!address.trim()) {
      setError({ message: "주소를 먼저 입력하세요." });
      return;
    }
    setLoading(true);
    setError(null);
    setData(null);
    try {
      setData(await analyze(address, useType));
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
          <span className="block text-slate-500 mb-1">건물 용도</span>
          <select
            value={useType}
            onChange={(e) => setUseType(e.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-2 bg-white"
          >
            {USE_TYPES.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </label>
        <button
          onClick={run}
          disabled={loading}
          className="px-4 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50"
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
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">항목</th>
                  <th className="text-right px-3 py-2 font-medium">값</th>
                  <th className="text-right px-3 py-2 font-medium">전국 평균</th>
                  <th className="text-left px-3 py-2 font-medium">출처 · 연도</th>
                </tr>
              </thead>
              <tbody>
                {data.facts.map((f, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-3 py-2 text-slate-800">{f.item}</td>
                    <td className="px-3 py-2 text-right font-semibold text-slate-900">
                      {fmt(f.value)}{f.unit}
                    </td>
                    <td className="px-3 py-2 text-right text-slate-500">
                      {f.national_avg != null ? fmt(f.national_avg) : "—"}{f.national_avg != null ? f.unit : ""}
                    </td>
                    <td className="px-3 py-2 text-slate-400 text-xs">
                      {f.source_tbl} · {f.year}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 시사점 */}
          {data.implications.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-2">참고 시사점</h3>
              <ul className="space-y-1.5">
                {data.implications.map((im, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <Badge tone="amber">{im.tag}</Badge>
                    <span>{im.text}<span className="text-slate-400"> · {im.basis}</span></span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 한 문단 */}
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-slate-700">초안 문단</h3>
              <CopyButton text={data.draft_paragraph} />
            </div>
            <p className="text-sm leading-relaxed text-slate-800 whitespace-pre-wrap">
              {data.draft_paragraph}
            </p>
          </div>

          <Notes notes={data.notes} />
        </div>
      )}
    </div>
  );
}
