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
          className="px-4 py-2 font-medium disabled:opacity-50"
          style={{background:'var(--brand)',color:'#fff',borderRadius:'var(--radius-sm)'}}
          onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background='var(--brand-hover)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background='var(--brand)'; }}
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
            <h3 className="text-sm font-semibold mb-2" style={{color:'var(--body)'}}>개별공시지가</h3>
            {data.land_price.price_per_sqm != null ? (
              <div
                className="p-4"
                style={{
                  border:'1px solid var(--hairline)',
                  borderRadius:'var(--radius)',
                  background:'var(--canvas-elevated)',
                }}
              >
                <div className="flex flex-wrap gap-6 items-end mb-2">
                  <div>
                    <span className="text-xs block mb-0.5" style={{color:'var(--mute)'}}>공시지가</span>
                    <span className="text-2xl font-bold" style={{color:'var(--ink)'}}>
                      {data.land_price.price_per_sqm.toLocaleString("ko-KR")}
                    </span>
                    <span className="text-sm ml-1" style={{color:'var(--body)'}}>원/㎡</span>
                    <span
                      className="ml-2 inline-block px-2.5 py-0.5 text-xs font-medium"
                      style={{
                        border:'1px solid var(--hairline)',
                        borderRadius:'var(--radius-sm)',
                        color:'var(--mute)',
                        background:'var(--canvas-elevated)',
                      }}
                    >
                      {data.land_price.year}년 기준
                    </span>
                  </div>
                </div>
                <p className="text-sm" style={{color:'var(--body)'}}>{data.land_price.addr}</p>
                <p className="text-xs mt-0.5" style={{color:'var(--mute)'}}>
                  {data.land_price.jibun} · {data.land_price.source}
                </p>
              </div>
            ) : (
              <p className="text-sm" style={{color:'var(--mute)'}}>공시지가 데이터 없음</p>
            )}
          </section>

          {/* 2. 건축물대장 */}
          <section>
            <h3 className="text-sm font-semibold mb-2" style={{color:'var(--body)'}}>건축물대장</h3>
            {(data.building.purpose != null || data.building.name != null) ? (
              <div
                className="overflow-x-auto"
                style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius)'}}
              >
                <table className="w-full text-sm">
                  <tbody>
                    {data.building.name && (
                      <tr style={{borderBottom:'1px solid var(--hairline)'}}>
                        <td className="px-3 py-2 w-28 whitespace-nowrap" style={{color:'var(--mute)'}}>건물명</td>
                        <td className="px-3 py-2 font-semibold" style={{color:'var(--ink)'}}>{data.building.name}</td>
                      </tr>
                    )}
                    <tr style={{borderBottom:'1px solid var(--hairline)'}}>
                      <td className="px-3 py-2" style={{color:'var(--mute)'}}>주용도</td>
                      <td className="px-3 py-2" style={{color:'var(--body)'}}>{data.building.purpose ?? "—"}</td>
                    </tr>
                    <tr style={{borderBottom:'1px solid var(--hairline)'}}>
                      <td className="px-3 py-2" style={{color:'var(--mute)'}}>규모</td>
                      <td className="px-3 py-2" style={{color:'var(--body)'}}>
                        지상 {data.building.floors_above ?? "—"}층 · 지하 {data.building.floors_below ?? "—"}층
                      </td>
                    </tr>
                    <tr style={{borderBottom:'1px solid var(--hairline)'}}>
                      <td className="px-3 py-2" style={{color:'var(--mute)'}}>사용승인</td>
                      <td className="px-3 py-2" style={{color:'var(--body)'}}>
                        {data.building.year_built != null ? `${data.building.year_built}년` : "—"}
                      </td>
                    </tr>
                    <tr style={{borderBottom:'1px solid var(--hairline)'}}>
                      <td className="px-3 py-2" style={{color:'var(--mute)'}}>연면적</td>
                      <td className="px-3 py-2" style={{color:'var(--body)'}}>{fmtNum(data.building.total_area_sqm)} ㎡</td>
                    </tr>
                    <tr style={{borderBottom:'1px solid var(--hairline)'}}>
                      <td className="px-3 py-2" style={{color:'var(--mute)'}}>대지면적</td>
                      <td className="px-3 py-2" style={{color:'var(--body)'}}>{fmtNum(data.building.site_area_sqm)} ㎡</td>
                    </tr>
                    <tr style={{borderBottom:'1px solid var(--hairline)'}}>
                      <td className="px-3 py-2" style={{color:'var(--mute)'}}>건폐율</td>
                      <td className="px-3 py-2" style={{color:'var(--body)'}}>{fmtNum(data.building.bcr)} %</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2" style={{color:'var(--mute)'}}>용적률</td>
                      <td className="px-3 py-2" style={{color:'var(--body)'}}>{fmtNum(data.building.far)} %</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm" style={{color:'var(--mute)'}}>건축물대장 데이터 없음</p>
            )}
            <p className="text-xs mt-1" style={{color:'var(--mute)'}}>{data.building.source}</p>
          </section>

          {/* 3. 실거래 */}
          <section>
            <h3 className="text-sm font-semibold mb-2" style={{color:'var(--body)'}}>
              최근 실거래{" "}
              <span className="font-normal text-xs" style={{color:'var(--mute)'}}>{data.real_estate.period}</span>
            </h3>
            {data.real_estate.transactions.length > 0 ? (
              <div
                className="overflow-x-auto"
                style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius)'}}
              >
                <table className="w-full text-sm">
                  <thead style={{background:'var(--canvas)',color:'var(--mute)'}}>
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
                      <tr key={i} style={{borderTop:'1px solid var(--hairline)'}}>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <Badge tone={t.deal_type === "매매" ? "blue" : "amber"}>{t.category}</Badge>
                        </td>
                        <td className="px-3 py-2 max-w-[120px] truncate" style={{color:'var(--body)'}}>{t.name || "—"}</td>
                        <td className="px-3 py-2 text-right whitespace-nowrap" style={{color:'var(--body)'}}>
                          {t.area_sqm != null ? `${fmtNum(t.area_sqm)} ㎡` : "—"}
                        </td>
                        <td className="px-3 py-2 text-right font-semibold whitespace-nowrap" style={{color:'var(--ink)'}}>
                          {fmtMoney(t.price_10k)}
                          {t.monthly_10k ? (
                            <span className="font-normal" style={{color:'var(--body)'}}> / {t.monthly_10k.toLocaleString("ko-KR")}만</span>
                          ) : null}
                        </td>
                        <td className="px-3 py-2 text-right" style={{color:'var(--body)'}}>
                          {t.floor != null ? `${t.floor}층` : "—"}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap" style={{color:'var(--body)'}}>{fmtYm(t.deal_ym)}</td>
                        <td className="px-3 py-2 text-xs" style={{color:'var(--mute)'}}>{t.dong || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm" style={{color:'var(--mute)'}}>해당 시군구 최근 거래 없음</p>
            )}
            <p className="text-xs mt-1" style={{color:'var(--mute)'}}>
              {data.real_estate.note} · {data.real_estate.source}
            </p>
          </section>

          {/* 4. 재해위험 */}
          {data.hazards && (
            <section>
              <h3 className="text-sm font-semibold mb-2" style={{color:'var(--body)'}}>
                재해위험{" "}
                {data.hazards.base_year && (
                  <span className="font-normal text-xs" style={{color:'var(--mute)'}}>{data.hazards.base_year}년 위험지도</span>
                )}
              </h3>
              <div className="flex flex-wrap gap-2">
                {[
                  { key: "flood", label: "홍수" },
                  { key: "landslide", label: "산사태" },
                ].map(({ key, label }) => {
                  const z = data.hazards[key] || {};
                  const inZone = z.in_zone;
                  return (
                    <div
                      key={key}
                      className="px-3 py-2 text-sm"
                      style={{
                        border: inZone === true ? '1px solid var(--warn)' : '1px solid var(--hairline)',
                        borderLeft: inZone === true ? '3px solid var(--warn)' : inZone === false ? '3px solid var(--ok)' : '1px solid var(--hairline)',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--canvas-elevated)',
                      }}
                    >
                      <span className="font-medium" style={{color:'var(--body)'}}>{label}위험</span>{" "}
                      <span
                        style={{
                          color: inZone === true ? 'var(--warn)' : inZone === false ? 'var(--ok)' : 'var(--mute)',
                          fontWeight: inZone === true ? 600 : undefined,
                        }}
                      >
                        {inZone === true ? "영향범위 포함" : inZone === false ? "영향범위 외" : "확인 불가"}
                      </span>
                      {z.affected_dong_count != null && (
                        <span className="text-xs" style={{color:'var(--mute)'}}> · 시군구 내 {z.affected_dong_count}개 동</span>
                      )}
                      {z.exposures && z.exposures.length > 0 && (
                        <div className="mt-1 space-y-0.5">
                          <span className="text-xs" style={{color:'var(--mute)'}}>
                            영향범위 내 {z.exposure_scope && `(${z.exposure_scope} 기준)`}
                          </span>
                          {z.exposures.map((e, j) => (
                            <div key={j} className="text-xs" style={{color:'var(--body)'}}>
                              {e.metric}{" "}
                              <span className="font-medium" style={{color:'var(--ink)'}}>
                                {e.affected != null ? e.affected.toLocaleString("ko-KR") : "—"}
                              </span>
                              {e.total != null && (
                                <span style={{color:'var(--mute)'}}>
                                  {" / "}{e.total.toLocaleString("ko-KR")}{e.unit}
                                  {e.total > 0 && e.affected != null &&
                                    ` (${Math.round((e.affected / e.total) * 100)}%)`}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
                {/* 폭염특보 이력 */}
                {data.hazards.heatwave && (
                  <div
                    className="px-3 py-2 text-sm"
                    style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius-sm)',background:'var(--canvas-elevated)'}}
                  >
                    <span className="font-medium" style={{color:'var(--body)'}}>폭염특보</span>{" "}
                    <span className="font-semibold" style={{color:'var(--warn)'}}>
                      경보 {data.hazards.heatwave.alert_count}
                    </span>
                    <span style={{color:'var(--body)'}}> · 주의보 {data.hazards.heatwave.warning_count}건</span>
                    <span className="block text-xs mt-0.5" style={{color:'var(--mute)'}}>
                      {data.hazards.heatwave.base_period}
                      {data.hazards.heatwave.scope && ` · ${data.hazards.heatwave.scope} 기준`}
                    </span>
                  </div>
                )}
              </div>
              <p className="text-xs mt-1" style={{color:'var(--mute)'}}>
                {data.hazards.dong_name && `${data.hazards.dong_name} 기준 · `}
                {data.hazards.note} · {data.hazards.source}
              </p>
            </section>
          )}

          <Notes notes={data.notes} />
        </div>
      )}
    </div>
  );
}
