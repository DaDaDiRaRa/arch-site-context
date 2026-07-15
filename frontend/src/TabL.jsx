import { useState } from "react";
import { kdbmDeck } from "./api.js";
import { Spinner, ErrorBox } from "./ui.jsx";

const SLIDES = [
  ["광역입지현황", "대지개요 + 다중반경 + 역세권(지하철 호선색)"],
  ["건물 용도현황", "주변 건물을 용도별 색(주거·상업·업무·공업·공공)"],
  ["입지현황", "주변 건물 매싱을 실측 높이별 색 + 이름·층수·높이"],
  ["방향별 조망 분석", "방향별 건물높이로 조망·차폐 아크링"],
];

export default function TabL({ address }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  async function generate() {
    if (!address.trim()) return setError({ message: "주소를 먼저 입력하세요." });
    setLoading(true); setError(null); setDone(false);
    try {
      const blob = await kdbmDeck(address);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `KDBM_대지분석_${address.replace(/\s+/g, "")}.pptx`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      setDone(true);
    } catch (e) { setError(e); } finally { setLoading(false); }
  }

  return (
    <div>
      <p className="text-sm mb-4" style={{ color: "var(--mute)" }}>
        <b>대지분석 덱 (KDBM)</b> — 주소 한 줄로 건원 KDBM 사전브리프 양식의 대지분석 4종을
        <b> 편집가능 A3 PPT</b>로 자동 생성합니다. 위성·건물 매싱(실측 높이)·용도·조망·역세권 —
        전부 실데이터(VWorld·kakao)이며 도형·표는 PowerPoint에서 손질 가능합니다.
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
        {loading ? "생성 중…" : "KDBM 덱 생성 · 다운로드"}
      </button>

      {loading && (
        <div className="mt-4 flex items-center gap-2 text-sm" style={{ color: "var(--mute)" }}>
          <Spinner /> 4종 지도 렌더 중 — <b>약 1분</b> 소요 (건물 매싱·위성 4장). 잠시만요…
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
