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
