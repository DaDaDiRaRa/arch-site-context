import { useState } from "react";
import { generateDeck } from "./api.js";
import { Spinner, ErrorBox } from "./ui.jsx";

const SLIDES = [
  ["광역입지현황", "대지개요 + 다중반경 + 역세권(지하철 호선색)"],
  ["건물 용도현황", "주변 건물을 용도별 색(주거·상업·업무·공업·공공)"],
  ["입지현황", "주변 건물 매싱을 실측 높이별 색 + 이름·층수·높이"],
  ["방향별 조망 분석", "방향별 건물높이로 조망·차폐 아크링"],
  ["지역통계", "인구·가구 지표 + 전국=100 + 참고 시사점"],
  ["수급진단", "인구 수요 × 시설 공급 교차 (참고)"],
  ["대지정보", "공시지가·건폐/용적률·재해·실거래"],
  ["생활맥락", "상권·학교·문화·부동산·생활인구 합본"],
  ["주변현황도", "반경 내 교통·교육·여가·주거·관공서 현황"],
  ["주변시설 (요약 + 종류별)", "종류별 개수 + 어린이집·경로당·병원… 각 1장(지도 핀·이름·거리)"],
];

export default function TabL({ address }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  async function generate() {
    if (!address.trim()) return setError({ message: "주소를 먼저 입력하세요." });
    setLoading(true); setError(null); setDone(false);
    try {
      const blob = await generateDeck(address);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `대지분석_${address.replace(/\s+/g, "")}.pptx`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      setDone(true);
    } catch (e) { setError(e); } finally { setLoading(false); }
  }

  return (
    <div>
      <p className="text-sm mb-4" style={{ color: "var(--mute)" }}>
        <b>대지분석 덱</b> — 주소 한 줄로 <b>지도 + 데이터 + 시설 상세</b>를 한 번에
        <b> 편집가능 A3 PPT</b>로 자동 생성합니다. 위성·건물 매싱·용도·조망 지도에 더해
        지역통계·수급진단·대지정보·생활맥락·주변현황도, 그리고 <b>시설 종류마다 지도·이름·거리 상세 1장씩</b> —
        전부 실데이터(VWorld·kakao·KOSIS·SGIS)이며 도형·표는 PowerPoint에서 손질 가능합니다.
      </p>

      <div className="grid grid-cols-2 gap-3 mb-5">
        {SLIDES.map(([t, d], i) => (
          <div key={i} className="rounded-lg p-3" style={{ background: "var(--card)", border: "1px solid var(--hairline)" }}>
            <div className="text-sm font-semibold" style={{ color: "var(--ink)" }}>{i + 1}. {t}</div>
            <div className="text-xs mt-1" style={{ color: "var(--mute)" }}>{d}</div>
          </div>
        ))}
      </div>

      <button
        onClick={generate}
        disabled={loading}
        className="px-5 py-2.5 rounded-md text-sm font-semibold"
        style={{ background: loading ? "var(--hairline)" : "var(--brand)", color: "#fff", cursor: loading ? "default" : "pointer" }}
      >
        {loading ? "생성 중…" : "덱 생성 · 다운로드"}
      </button>

      {loading && (
        <div className="mt-4 flex items-center gap-2 text-sm" style={{ color: "var(--mute)" }}>
          <Spinner /> 지도 4종 + 데이터 6종 조립 중 — <b>약 2~3분</b> 소요 (건물 매싱·위성·통합분석). 잠시만요…
        </div>
      )}
      {done && !loading && (
        <div className="mt-4 text-sm" style={{ color: "var(--brand)" }}>
          ✓ 다운로드 완료 — PowerPoint에서 열어 편집하세요. (도형·표·라벨 모두 네이티브)
        </div>
      )}
      {error && <div className="mt-4"><ErrorBox error={error} /></div>}

      <p className="text-xs mt-6" style={{ color: "var(--mute)", fontFamily: "var(--font-mono)" }}>
        건물 높이·매싱: arch-site-model(VWorld 실측층수) · 용도: 주변시설 추정 · 도로폭: 소스 미확보(수작업)
      </p>
    </div>
  );
}
