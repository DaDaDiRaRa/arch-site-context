import { useState, useEffect } from "react";
import { getHistory, downloadHistory } from "./api.js";
import { Spinner, ErrorBox } from "./ui.jsx";

const KIND = {
  deck: { label: "대지분석 덱", color: "var(--brand)" },
  board: { label: "종합읽기", color: "#2AA198" },
};

function fmtSize(n) {
  if (!n) return "";
  const mb = n / (1024 * 1024);
  return mb >= 1 ? `${mb.toFixed(1)}MB` : `${Math.max(1, Math.round(n / 1024))}KB`;
}
function fmtDate(s) {
  return (s || "").replace("T", " ").slice(0, 16);
}

export default function TabHistory() {
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dl, setDl] = useState(null);

  async function load() {
    setLoading(true); setError(null);
    try { const r = await getHistory(); setItems(r.items || []); }
    catch (e) { setError(e); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function download(it) {
    setDl(it.id); setError(null);
    try { await downloadHistory(it.id, it.filename); }
    catch (e) { setError(e); } finally { setDl(null); }
  }

  const anyLocal = (items || []).some((it) => it.backend !== "gcs");

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm" style={{ color: "var(--mute)" }}>
          만든 <b>대지분석 덱 · 종합읽기 PPT</b>를 보관합니다 — 재생성 없이 다시 내려받기.
        </p>
        <button
          onClick={load}
          disabled={loading}
          className="px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--canvas-elevated)", color: "var(--brand)", border: "1px solid var(--brand)", borderRadius: "var(--radius-sm)" }}
        >
          {loading ? "새로고침…" : "새로고침 ↻"}
        </button>
      </div>

      {anyLocal && (
        <p className="text-xs mb-3" style={{ color: "var(--warn)" }}>
          ⚠ 일부 항목이 임시 저장(서버 재시작 시 사라짐)입니다. 영구 보관하려면 <code>GCS_CACHE_BUCKET</code> 설정이 필요합니다.
        </p>
      )}

      {error && <div className="mb-3"><ErrorBox error={error} /></div>}
      {loading && !items && <div className="flex items-center gap-2 text-sm" style={{ color: "var(--mute)" }}><Spinner /> 불러오는 중…</div>}
      {items && items.length === 0 && (
        <div className="text-sm py-8 text-center" style={{ color: "var(--mute)" }}>
          아직 생성한 PPT가 없습니다. <b>대지분석 덱(L)</b>·<b>종합읽기(I)</b>에서 만들면 여기 쌓입니다.
        </div>
      )}

      <div className="space-y-2">
        {(items || []).map((it) => {
          const k = KIND[it.kind] || { label: it.kind, color: "var(--mute)" };
          return (
            <div key={it.id} className="flex items-center gap-3 rounded-lg p-3"
                 style={{ background: "var(--card)", border: "1px solid var(--hairline)" }}>
              <span className="text-xs font-semibold px-2 py-1 rounded"
                    style={{ background: k.color, color: "#fff", whiteSpace: "nowrap" }}>{k.label}</span>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate" style={{ color: "var(--ink)" }}>{it.title}</div>
                <div className="text-xs mt-0.5" style={{ color: "var(--mute)" }}>
                  {fmtDate(it.created)} · {(it.params?.use_type) || ""} · 반경 {it.params?.radius}m · {fmtSize(it.size)}
                  {it.backend !== "gcs" && <span style={{ color: "var(--warn)" }}> · 임시</span>}
                </div>
              </div>
              <button
                onClick={() => download(it)}
                disabled={dl === it.id}
                className="px-3 py-1.5 text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--brand)", color: "#fff", borderRadius: "var(--radius-sm)", whiteSpace: "nowrap" }}
              >
                {dl === it.id ? "받는 중…" : "다운로드 ↓"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
