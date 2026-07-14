import { useState } from "react";
import TabA from "./TabA.jsx";
import TabB from "./TabB.jsx";
import TabC from "./TabC.jsx";
import TabD from "./TabD.jsx";
import TabE from "./TabE.jsx";
import TabF from "./TabF.jsx";
import TabG from "./TabG.jsx";
import TabH from "./TabH.jsx";
import TabI from "./TabI.jsx";
import TabJ from "./TabJ.jsx";

export default function App() {
  const [address, setAddress] = useState("");
  const [tab, setTab] = useState("I");
  const [inputFocused, setInputFocused] = useState(false);

  return (
    <div className="min-h-screen" style={{backgroundColor:'var(--canvas-elevated)',color:'var(--ink)'}}>
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* 헤더 */}
        <header className="mb-6">
          <h1 style={{fontSize:24,fontWeight:600,letterSpacing:'-0.02em',color:'var(--ink)'}}>
            터읽기 <span style={{color:'var(--brand)'}}>·</span>
            <span className="text-base font-normal ml-2" style={{color:'var(--mute)'}}>대지 맥락 읽기</span>
          </h1>
          <p className="text-sm mt-1" style={{color:'var(--mute)',fontSize:13}}>
            주소 한 줄로 지역 통계와 주변 시설을 읽어드립니다. 최종 판단은 사람이.
          </p>
        </header>

        {/* 주소 입력 (공통 — 비교 탭은 자체 다중입력 사용) */}
        <div className={`mb-5 ${tab === "D" ? "hidden" : ""}`}>
          <label
            className="block mb-1"
            style={{color:'var(--mute)',fontSize:12,fontFamily:'var(--font-mono)',letterSpacing:'0.06em',textTransform:'uppercase'}}
          >
            대지 주소
          </label>
          <input
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="예) 서울 영등포구 여의대로 24"
            className="w-full px-4 py-2.5 focus:outline-none"
            style={{
              border: `1px solid ${inputFocused ? 'var(--brand)' : 'var(--hairline)'}`,
              borderRadius: 'var(--radius-sm)',
              fontSize: 14,
              color: 'var(--ink)',
              background: 'var(--canvas-elevated)',
            }}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
          />
        </div>

        {/* 탭 */}
        <div className="flex gap-1 mb-5" style={{borderBottom:'1px solid var(--hairline)'}}>
          {[
            ["I", "종합 읽기"],
            ["A", "지역 통계"],
            ["B", "주변 시설"],
            ["C", "수급진단"],
            ["D", "후보지 비교"],
            ["E", "물어보기"],
            ["F", "대지 정보"],
            ["G", "보드 합본"],
            ["H", "공동주택 readout"],
            ["J", "심의 현황팩"],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className="px-4 py-2.5 text-sm font-medium -mb-px border-b-2 border-transparent"
              style={tab === key
                ? {borderBottomColor:'var(--brand)',color:'var(--brand)'}
                : {color:'var(--mute)'}}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 탭 내용 (마운트 유지로 입력 상태 보존) */}
        <div className={tab === "I" ? "" : "hidden"}>
          <TabI address={address} />
        </div>
        <div className={tab === "A" ? "" : "hidden"}>
          <TabA address={address} />
        </div>
        <div className={tab === "B" ? "" : "hidden"}>
          <TabB address={address} />
        </div>
        <div className={tab === "C" ? "" : "hidden"}>
          <TabC address={address} />
        </div>
        <div className={tab === "D" ? "" : "hidden"}>
          <TabD />
        </div>
        <div className={tab === "E" ? "" : "hidden"}>
          <TabE address={address} />
        </div>
        <div className={tab === "F" ? "" : "hidden"}>
          <TabF address={address} />
        </div>
        <div className={tab === "G" ? "" : "hidden"}>
          <TabG address={address} />
        </div>
        <div className={tab === "H" ? "" : "hidden"}>
          <TabH address={address} />
        </div>
        <div className={tab === "J" ? "" : "hidden"}>
          <TabJ address={address} />
        </div>

        <footer className="mt-10" style={{color:'var(--mute)',fontFamily:'var(--font-mono)',fontSize:11}}>
          통계: 시군구 평균(KOSIS) · 시설: 카카오 · 위성: VWorld · 수치는 코드/규칙, 표현만 AI
        </footer>
      </div>
    </div>
  );
}
