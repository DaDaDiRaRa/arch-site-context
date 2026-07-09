import { useState } from "react";

export function Spinner({ label = "불러오는 중…" }) {
  return (
    <div className="flex items-center gap-2 text-sm py-6" style={{color:'var(--mute)'}}>
      <span
        className="inline-block w-4 h-4 border-2 rounded-full animate-spin"
        style={{borderColor:'var(--hairline)',borderTopColor:'var(--brand)'}}
      />
      {label}
    </div>
  );
}

export function ErrorBox({ error }) {
  if (!error) return null;
  const isBlock = !!error.code;
  return (
    <div
      className="px-4 py-3 text-sm"
      style={{
        border: isBlock ? '1px solid var(--warn)' : '1px solid var(--error)',
        borderLeft: isBlock ? '3px solid var(--warn)' : '3px solid var(--error)',
        borderRadius: 'var(--radius-sm)',
        background: 'var(--canvas-elevated)',
        color: 'var(--ink)',
      }}
    >
      <span className="font-semibold">{isBlock ? `확인 불가 (${error.code})` : "오류"}</span>
      <span className="ml-2">{error.message}</span>
    </div>
  );
}

export function Badge({ children, tone = "slate" }) {
  const colors = {
    slate: 'var(--mute)',
    blue:  'var(--brand)',
    green: 'var(--ok)',
    amber: 'var(--warn)',
  };
  return (
    <span
      className="inline-block rounded-full px-2.5 py-0.5"
      style={{
        border: '1px solid var(--hairline)',
        background: 'var(--canvas-elevated)',
        color: colors[tone] ?? 'var(--mute)',
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
      }}
    >
      {children}
    </span>
  );
}

// S1 — 데이터 근접도 등급 칩. 대지에 가까울수록 정밀(green), 시군구 평균이면 slate.
// 순수 메타데이터: "이 수치가 대지에 얼마나 가까운 단위에서 나왔나" (절대 원칙 4).
const PROX_TONE = { "대지": "green", "반경": "green", "읍면동": "blue", "시군구": "slate", "proxy": "amber" };
const PROX_TITLE = {
  "대지": "대지(필지) 값 — 가장 정밀",
  "반경": "반경 내 실측·집계 — 대지에 근접",
  "읍면동": "행정동 단위",
  "시군구": "시군구 평균 — 대지 고유값 아님",
  "proxy": "추정·대리값 — 참고",
};
export function ProximityChip({ level }) {
  if (!level) return null;
  return (
    <span title={PROX_TITLE[level] ?? ""}>
      <Badge tone={PROX_TONE[level] ?? "slate"}>{level}</Badge>
    </span>
  );
}

// T1 — 전국=100 정규화 지수 막대 (Esri US=100 방식). 중심선 100, 좌우 위치로 상회/하회 표시.
// 색은 중립(방향만 신호, 좋다/나쁘다 판정 아님). index null이면 "—".
export function IndexBar({ index }) {
  if (index == null) return <span style={{ color: "var(--hairline)" }}>—</span>;
  const LO = 40, HI = 160;
  const clamp = (v) => Math.max(LO, Math.min(HI, v));
  const pct = (v) => ((clamp(v) - LO) / (HI - LO)) * 100;
  const center = pct(100);
  const val = pct(index);
  const left = Math.min(center, val);
  const width = Math.abs(val - center);
  return (
    <span className="inline-flex items-center gap-2">
      <span style={{ position: "relative", display: "inline-block", width: 72, height: 8, background: "var(--canvas)", border: "1px solid var(--hairline)", borderRadius: 4 }}>
        <span style={{ position: "absolute", left: `${center}%`, top: -2, bottom: -2, width: 1, background: "var(--ink)" }} />
        <span style={{ position: "absolute", left: `${left}%`, width: `${width}%`, top: 1, bottom: 1, background: "var(--brand)", opacity: 0.5, borderRadius: 2 }} />
      </span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--body)" }}>{index}</span>
    </span>
  );
}

export function Notes({ notes }) {
  if (!notes || notes.length === 0) return null;
  return (
    <ul className="mt-3 text-xs list-disc pl-5 space-y-0.5" style={{color:'var(--mute)'}}>
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
      className="text-xs px-2.5 py-1"
      style={{
        border: '1px solid var(--hairline)',
        borderRadius: 'var(--radius-sm)',
        color: 'var(--mute)',
      }}
    >
      {done ? "복사됨" : "복사"}
    </button>
  );
}
