import { useState } from "react";

export function Spinner({ label = "불러오는 중…" }) {
  return (
    <div className="flex items-center gap-2 text-slate-500 text-sm py-6">
      <span className="inline-block w-4 h-4 border-2 border-slate-300 border-t-blue-600 rounded-full animate-spin" />
      {label}
    </div>
  );
}

export function ErrorBox({ error }) {
  if (!error) return null;
  const isBlock = !!error.code; // 데이터 하드블록
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${isBlock ? "border-amber-300 bg-amber-50 text-amber-800" : "border-red-300 bg-red-50 text-red-700"}`}>
      <span className="font-semibold">{isBlock ? `확인 불가 (${error.code})` : "오류"}</span>
      <span className="ml-2">{error.message}</span>
    </div>
  );
}

export function Badge({ children, tone = "slate" }) {
  const tones = {
    slate: "bg-slate-100 text-slate-700",
    blue: "bg-blue-100 text-blue-700",
    green: "bg-emerald-100 text-emerald-700",
    amber: "bg-amber-100 text-amber-700",
  };
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

export function Notes({ notes }) {
  if (!notes || notes.length === 0) return null;
  return (
    <ul className="mt-3 text-xs text-slate-500 list-disc pl-5 space-y-0.5">
      {notes.map((n, i) => (
        <li key={i}>{n}</li>
      ))}
    </ul>
  );
}

export function CopyButton({ text }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          /* clipboard 차단 환경 무시 */
        }
      }}
      className="text-xs px-2.5 py-1 rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50"
    >
      {done ? "복사됨 ✓" : "복사"}
    </button>
  );
}
