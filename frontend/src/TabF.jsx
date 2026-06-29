import { useState } from "react";
import { site } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes } from "./ui.jsx";

function fmtMoney(val10k) {
  if (val10k == null) return "—";
  if (val10k >= 10000) {
    const eok = Math.floor(val10k / 10000);
    const man = val10k % 10000;
    return man > 0
      ? `${eok.toLocaleString("ko-KR")}억 ${man.toLocaleString("ko-KR")}만원`
      : `${eok.toLocaleString("ko-KR")}억원`;
  }
  return `${val10k.toLocaleString("ko-KR")}만원`;
}

function fmtYm(ym) {
  if (!ym || ym.length < 6) return ym || "—";
  return `${ym.slice(0, 4)}년 ${parseInt(ym.slice(4, 6), 10)}월`;
}

function fmtNum(v, digits = 1) {
  if (v == null) return "—";
  return typeof v === "number"
    ? v.toLocaleString("ko-KR", { maximumFractionDigits: digits })
    : v;
}

export default function TabF({ address }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  async function run() {
    if (!address.trim()) { setError({ message: "주소를 먼저 입력하세요." }); return; }
    setLoading(true); setError(null); setData(null);
    try { setData(await site(address)); }
    catch (e) { setError(e); }
    finally { setLoading(false); }
  }

  return (
    <div>
      <div className="flex items-end gap-3">
        <button
          onClick={run}
          disabled={loading}
          className="px-4 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          대지 기본정보 조회
        </button>
      </div>

      {loading && <Spinner label="공시지가 · 건축물대장 · 실거래 조회 중…" />}
      <div className="mt-4"><ErrorBox error={error} /></div>

      {data && (
        <div className="mt-5 space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="blue">{data.center.sigungu || data.center.address}</Badge>
            {data.center.dong && <Badge>{data.center.dong}</Badge>}
            <Badge>{data.base_date}</Badge>
          </div>

          {/* 1. 개별공시지가 */}
          <section>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">개별공시지가</h3>
            {data.land_price.price_per_sqm != null ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap gap-6 items-end mb-2">
                  <div>
                    <span className="text-xs text-slate-500 block mb-0.5">공시지가</span>
                    <span className="text-2xl font-bold text-slate-900">
                      {data.land_price.price_per_sqm.toLocaleString("ko-KR")}
                    </span>
                    <span className="text-sm text-slate-600 ml-1">원/㎡</span>
                    <span className="ml-2 inline-block rounded-full px-2.5 py-0.5 text-xs font-medium bg-slate-100 text-slate-700">
                      {data.land_price.year}년 기준
                    </span>
                  </div>
                </div>
                <p className="text-sm text-slate-600">{data.land_price.addr}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {data.land_price.jibun} · {data.land_price.source}
                </p>
              </div>
            ) : (
              <p className="text-sm text-slate-400">공시지가 데이터 없음</p>
            )}
          </section>

          {/* 2. 건축물대장 */}
          <section>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">건축물대장</h3>
            {(data.building.purpose != null || data.building.name != null) ? (
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="w-full text-sm">
                  <tbody>
                    {data.building.name && (
                      <tr className="border-b border-slate-100">
                        <td className="px-3 py-2 text-slate-500 w-28 whitespace-nowrap">건물명</td>
                        <td className="px-3 py-2 font-semibold text-slate-900">{data.building.name}</td>
                      </tr>
                    )}
                    <tr className="border-b border-slate-100">
                      <td className="px-3 py-2 text-slate-500">주용도</td>
                      <td className="px-3 py-2 text-slate-800">{data.building.purpose ?? "—"}</td>
                    </tr>
                    <tr className="border-b border-slate-100">
                      <td className="px-3 py-2 text-slate-500">규모</td>
                      <td className="px-3 py-2 text-slate-800">
                        지상 {data.building.floors_above ?? "—"}층 · 지하 {data.building.floors_below ?? "—"}층
                      </td>
                    </tr>
                    <tr className="border-b border-slate-100">
                      <td className="px-3 py-2 text-slate-500">사용승인</td>
                      <td className="px-3 py-2 text-slate-800">
                        {data.building.year_built != null ? `${data.building.year_built}년` : "—"}
                      </td>
                    </tr>
                    <tr className="border-b border-slate-100">
                      <td className="px-3 py-2 text-slate-500">연면적</td>
                      <td className="px-3 py-2 text-slate-800">{fmtNum(data.building.total_area_sqm)} ㎡</td>
                    </tr>
                    <tr className="border-b border-slate-100">
                      <td className="px-3 py-2 text-slate-500">대지면적</td>
                      <td className="px-3 py-2 text-slate-800">{fmtNum(data.building.site_area_sqm)} ㎡</td>
                    </tr>
                    <tr className="border-b border-slate-100">
                      <td className="px-3 py-2 text-slate-500">건폐율</td>
                      <td className="px-3 py-2 text-slate-800">{fmtNum(data.building.bcr)} %</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2 text-slate-500">용적률</td>
                      <td className="px-3 py-2 text-slate-800">{fmtNum(data.building.far)} %</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-slate-400">건축물대장 데이터 없음</p>
            )}
            <p className="text-xs text-slate-400 mt-1">{data.building.source}</p>
          </section>

          {/* 3. 실거래 */}
          <section>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">
              최근 실거래{" "}
              <span className="font-normal text-slate-400 text-xs">{data.real_estate.period}</span>
            </h3>
            {data.real_estate.transactions.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-500">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">종류</th>
                      <th className="text-left px-3 py-2 font-medium">이름</th>
                      <th className="text-right px-3 py-2 font-medium">면적</th>
                      <th className="text-right px-3 py-2 font-medium">금액</th>
                      <th className="text-right px-3 py-2 font-medium">층</th>
                      <th className="text-left px-3 py-2 font-medium">거래월</th>
                      <th className="text-left px-3 py-2 font-medium">동</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.real_estate.transactions.map((t, i) => (
                      <tr key={i} className="border-t border-slate-100">
                        <td className="px-3 py-2 whitespace-nowrap">
                          <Badge tone={t.deal_type === "매매" ? "blue" : "amber"}>{t.category}</Badge>
                        </td>
                        <td className="px-3 py-2 text-slate-800 max-w-[120px] truncate">{t.name || "—"}</td>
                        <td className="px-3 py-2 text-right text-slate-600 whitespace-nowrap">
                          {t.area_sqm != null ? `${fmtNum(t.area_sqm)} ㎡` : "—"}
                        </td>
                        <td className="px-3 py-2 text-right font-semibold text-slate-900 whitespace-nowrap">
                          {fmtMoney(t.price_10k)}
                          {t.monthly_10k ? (
                            <span className="text-slate-500 font-normal"> / {t.monthly_10k.toLocaleString("ko-KR")}만</span>
                          ) : null}
                        </td>
                        <td className="px-3 py-2 text-right text-slate-600">
                          {t.floor != null ? `${t.floor}층` : "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-600 whitespace-nowrap">{fmtYm(t.deal_ym)}</td>
                        <td className="px-3 py-2 text-slate-500 text-xs">{t.dong || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-slate-400">해당 시군구 최근 거래 없음</p>
            )}
            <p className="text-xs text-slate-400 mt-1">
              {data.real_estate.note} · {data.real_estate.source}
            </p>
          </section>

          <Notes notes={data.notes} />
        </div>
      )}
    </div>
  );
}
