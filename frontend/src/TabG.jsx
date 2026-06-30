import { useState } from "react";
import { seed } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes } from "./ui.jsx";

const RADII = [500, 1000, 2000];

function fmtPeriod(ym) {
  if (!ym || ym.length < 6) return ym || "";
  return `${ym.slice(0, 4)}년 ${parseInt(ym.slice(4, 6), 10)}월`;
}

function fmtDate(d) {
  if (!d || d.length < 8) return d || "";
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
}

function Block({ title, badge, source, empty, children }) {
  return (
    <div
      className="p-4"
      style={{
        border: '1px solid var(--hairline)',
        borderRadius: 'var(--radius)',
        background: 'var(--canvas-elevated)',
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        <h4 className="text-sm font-semibold" style={{color: empty ? 'var(--mute)' : 'var(--body)'}}>{title}</h4>
        {badge && <Badge tone="slate">{badge}</Badge>}
      </div>
      {empty ? (
        <p className="text-xs" style={{color:'var(--mute)'}}>데이터 없음</p>
      ) : (
        <>
          {children}
          {source && <p className="text-xs mt-2" style={{color:'var(--mute)'}}>{source}</p>}
        </>
      )}
    </div>
  );
}

export default function TabG({ address }) {
  const [radius, setRadius] = useState(1000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  async function run() {
    if (!address.trim()) { setError({ message: "주소를 먼저 입력하세요." }); return; }
    setLoading(true); setError(null); setData(null);
    try { setData(await seed(address, radius)); }
    catch (e) { setError(e); }
    finally { setLoading(false); }
  }

  const ctx = data?.context;

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span
            className="block mb-1"
            style={{color:'var(--mute)',fontSize:11,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
          >
            상권 반경
          </span>
          <div className="flex gap-1">
            {RADII.map((r) => (
              <button
                key={r}
                onClick={() => setRadius(r)}
                className="px-3 py-1.5 text-sm font-medium"
                style={{
                  border: radius === r ? '1px solid var(--brand)' : '1px solid var(--hairline)',
                  borderRadius: 'var(--radius-sm)',
                  background: radius === r ? 'var(--brand)' : 'var(--canvas-elevated)',
                  color: radius === r ? '#fff' : 'var(--body)',
                }}
              >
                {r >= 1000 ? `${r / 1000}km` : `${r}m`}
              </button>
            ))}
          </div>
        </label>
        <button
          onClick={run}
          disabled={loading}
          className="px-4 py-2 font-medium disabled:opacity-50"
          style={{background:'var(--brand)',color:'#fff',borderRadius:'var(--radius-sm)'}}
          onMouseEnter={(e) => { if (!loading) e.currentTarget.style.background='var(--brand-hover)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background='var(--brand)'; }}
        >
          보드 조회
        </button>
      </div>

      {loading && <Spinner label="상권 · 학교 · 날씨 등 조회 중…" />}
      <div className="mt-4"><ErrorBox error={error} /></div>

      {data && (
        <div className="mt-5 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="blue">{data.site.sigungu}</Badge>
            {data.site.eupmyeondong && <Badge>{data.site.eupmyeondong}</Badge>}
            <Badge>{data.base_date}</Badge>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

            {/* 상권 */}
            <Block
              title={`상권 (반경 ${ctx?.stores?.radius ?? radius}m)`}
              source={ctx?.stores ? "소상공인시장진흥공단 B553077" : null}
              empty={!ctx?.stores}
            >
              <p className="text-2xl font-bold mb-2" style={{color:'var(--ink)'}}>
                {ctx.stores?.total?.toLocaleString("ko-KR")}
                <span className="text-sm font-normal ml-1" style={{color:'var(--body)'}}>개 점포</span>
              </p>
              <ul className="space-y-0.5">
                {(ctx.stores?.by_large || []).slice(0, 6).map(([nm, cnt]) => (
                  <li key={nm} className="flex justify-between text-sm">
                    <span style={{color:'var(--body)'}}>{nm}</span>
                    <span className="font-medium" style={{color:'var(--ink)'}}>{cnt?.toLocaleString("ko-KR")}개</span>
                  </li>
                ))}
              </ul>
            </Block>

            {/* 학교 */}
            <Block
              title={`학교 (${ctx?.schools?.scope ?? data.site.sigungu})`}
              source={ctx?.schools ? "교육부 NEIS" : null}
              empty={!ctx?.schools}
            >
              <p className="text-2xl font-bold mb-2" style={{color:'var(--ink)'}}>
                {ctx.schools?.count}
                <span className="text-sm font-normal ml-1" style={{color:'var(--body)'}}>개교</span>
              </p>
              <ul className="space-y-0.5">
                {Object.entries(ctx.schools?.by_level || {}).map(([lv, cnt]) => (
                  <li key={lv} className="flex justify-between text-sm">
                    <span style={{color:'var(--body)'}}>{lv}</span>
                    <span className="font-medium" style={{color:'var(--ink)'}}>{cnt}개</span>
                  </li>
                ))}
              </ul>
            </Block>

            {/* 어린이집 */}
            <Block
              title={`어린이집 (${ctx?.childcare?.scope ?? data.site.sigungu})`}
              source={ctx?.childcare ? "정보공개포털 cpmsapi021" : null}
              empty={!ctx?.childcare}
            >
              <div className="flex gap-8">
                <div>
                  <span className="text-xs block mb-0.5" style={{color:'var(--mute)'}}>개소</span>
                  <span className="text-2xl font-bold" style={{color:'var(--ink)'}}>{ctx.childcare?.count}</span>
                  <span className="text-sm ml-1" style={{color:'var(--body)'}}>개</span>
                </div>
                {ctx.childcare?.total_capacity > 0 && (
                  <div>
                    <span className="text-xs block mb-0.5" style={{color:'var(--mute)'}}>총정원</span>
                    <span className="text-2xl font-bold" style={{color:'var(--ink)'}}>
                      {ctx.childcare?.total_capacity?.toLocaleString("ko-KR")}
                    </span>
                    <span className="text-sm ml-1" style={{color:'var(--body)'}}>명</span>
                  </div>
                )}
              </div>
              {ctx.childcare?.sample?.length > 0 && (
                <p className="text-xs mt-2" style={{color:'var(--mute)'}}>{ctx.childcare?.sample?.join(" · ")}</p>
              )}
            </Block>

            {/* 문화시설 */}
            <Block
              title={`문화시설 (${ctx?.culture?.scope ?? data.site.sigungu})`}
              source={ctx?.culture ? `문화기반시설총람 ${ctx.culture.pblshYr}년` : null}
              empty={!ctx?.culture}
            >
              <p className="text-2xl font-bold mb-2" style={{color:'var(--ink)'}}>
                {ctx.culture?.total}
                <span className="text-sm font-normal ml-1" style={{color:'var(--body)'}}>개소</span>
              </p>
              <ul className="space-y-0.5">
                {Object.entries(ctx.culture?.by_type || {}).map(([tp, cnt]) => (
                  <li key={tp} className="flex justify-between text-sm">
                    <span style={{color:'var(--body)'}}>{tp}</span>
                    <span className="font-medium" style={{color:'var(--ink)'}}>{cnt}개</span>
                  </li>
                ))}
              </ul>
            </Block>

            {/* 부동산지수 */}
            <Block
              title="부동산 매매가격지수"
              source={ctx?.real_estate_index ? `부동산원 R-ONE · ${fmtPeriod(ctx.real_estate_index.period)}` : null}
              empty={!ctx?.real_estate_index}
            >
              <p className="text-2xl font-bold" style={{color:'var(--ink)'}}>
                {ctx.real_estate_index?.value?.toFixed(1)}
                <span className="text-sm font-normal ml-1" style={{color:'var(--mute)'}}>pt (기준 100)</span>
              </p>
              <p className="text-sm mt-1" style={{color:'var(--body)'}}>
                {ctx.real_estate_index?.region} · {ctx.real_estate_index?.item}
              </p>
            </Block>

            {/* 날씨 */}
            <Block
              title="현재 날씨"
              source={ctx?.weather ? `기상청 단기예보 · ${fmtDate(ctx.weather.fcst_date)}` : null}
              empty={!ctx?.weather}
            >
              <div className="flex gap-6 items-end">
                {ctx.weather?.temp_c != null && (
                  <div>
                    <span className="text-xs block mb-0.5" style={{color:'var(--mute)'}}>기온</span>
                    <span className="text-2xl font-bold" style={{color:'var(--ink)'}}>{ctx.weather?.temp_c}°C</span>
                  </div>
                )}
                {ctx.weather?.sky && (
                  <div>
                    <span className="text-xs block mb-0.5" style={{color:'var(--mute)'}}>하늘</span>
                    <span className="text-lg" style={{color:'var(--body)'}}>{ctx.weather?.sky}</span>
                  </div>
                )}
                {ctx.weather?.pop_pct != null && (
                  <div>
                    <span className="text-xs block mb-0.5" style={{color:'var(--mute)'}}>강수확률</span>
                    <span className="text-lg" style={{color:'var(--body)'}}>{ctx.weather?.pop_pct}%</span>
                  </div>
                )}
              </div>
            </Block>

            {/* 생활인구 */}
            <Block
              title="생활인구 (서울 전용)"
              source={
                ctx?.living_population
                  ? `서울 열린데이터 · ${ctx.living_population.date} ${ctx.living_population.hour}시`
                  : null
              }
              empty={!ctx?.living_population}
              badge={!ctx?.living_population && !data.site.sgg_code?.startsWith("11") ? "비서울" : null}
            >
              <span className="text-2xl font-bold" style={{color:'var(--ink)'}}>
                {ctx.living_population?.value?.toLocaleString("ko-KR")}
              </span>
              <span className="text-sm ml-1" style={{color:'var(--body)'}}>명</span>
              <p className="text-xs mt-1" style={{color:'var(--mute)'}}>
                행정동 추계 · 서울시 기준 (참고)
              </p>
            </Block>

            {/* 공연시설 */}
            <Block
              title={`공연시설 (${ctx?.venues?.scope ?? data.site.sigungu})`}
              source={ctx?.venues ? "예술경영지원센터 KOPIS" : null}
              empty={!ctx?.venues}
            >
              <p className="text-2xl font-bold mb-2" style={{color:'var(--ink)'}}>
                {ctx.venues?.count}
                <span className="text-sm font-normal ml-1" style={{color:'var(--body)'}}>개소</span>
              </p>
              <ul className="space-y-0.5">
                {(ctx.venues?.venues || []).slice(0, 4).map((v, i) => (
                  <li key={i} className="text-sm flex justify-between" style={{color:'var(--body)'}}>
                    <span>{v.name}</span>
                    {v.hall_count != null && (
                      <span className="text-xs" style={{color:'var(--mute)'}}>{v.hall_count}관</span>
                    )}
                  </li>
                ))}
              </ul>
            </Block>
          </div>

          <Notes notes={ctx?.notes ?? []} />
        </div>
      )}
    </div>
  );
}
