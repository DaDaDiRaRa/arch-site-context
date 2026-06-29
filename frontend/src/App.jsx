import { useState } from "react";
import TabA from "./TabA.jsx";
import TabB from "./TabB.jsx";
import TabC from "./TabC.jsx";
import TabD from "./TabD.jsx";
import TabE from "./TabE.jsx";
import TabF from "./TabF.jsx";
import TabG from "./TabG.jsx";

export default function App() {
  const [address, setAddress] = useState("");
  const [tab, setTab] = useState("A");

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* 헤더 */}
        <header className="mb-6">
          <h1 className="text-2xl font-bold tracking-tight">
            터읽기 <span className="text-blue-600">·</span>
            <span className="text-base font-normal text-slate-500 ml-2">대지 맥락 읽기</span>
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            주소 한 줄로 지역 통계와 주변 시설을 읽어드립니다. 최종 판단은 사람이.
          </p>
        </header>

        {/* 주소 입력 (공통 — 비교 탭은 자체 다중입력 사용) */}
        <div className={`mb-5 ${tab === "D" ? "hidden" : ""}`}>
          <label className="block text-sm text-slate-500 mb-1">대지 주소</label>
          <input
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="예) 서울 영등포구 여의대로 24"
            className="w-full border border-slate-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* 탭 */}
        <div className="flex gap-1 border-b border-slate-200 mb-5">
          {[
            ["A", "지역 통계"],
            ["B", "주변 시설"],
            ["C", "수급진단"],
            ["D", "후보지 비교"],
            ["E", "물어보기"],
            ["F", "대지 정보"],
            ["G", "보드 합본"],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-2.5 text-sm font-medium -mb-px border-b-2 ${tab === key ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:text-slate-700"}`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 탭 내용 (마운트 유지로 입력 상태 보존) */}
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

        <footer className="mt-10 text-xs text-slate-400">
          통계: 시군구 평균(KOSIS) · 시설: 카카오 · 위성: VWorld · 수치는 코드/규칙, 표현만 AI
        </footer>
      </div>
    </div>
  );
}
