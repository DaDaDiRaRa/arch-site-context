import { useState } from "react";
import { board } from "./api.js";
import { Spinner, ErrorBox, Badge, Notes, ProximityChip } from "./ui.jsx";

const USE_TYPES = ["주거", "상업", "의료"];
const RESOLUTIONS = ["시군구", "읍면동", "반경"];
const RES_LABEL = { 시군구: "시군구(구)", 읍면동: "읍면동(동)", 반경: "반경(집계구)" };
const RADII = [500, 1000, 2000];

function ToggleBtn({ active, onClick, children, title }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="px-3 py-1.5 text-sm"
      style={{
        border: active ? "1px solid var(--brand)" : "1px solid var(--hairline)",
        borderRadius: "var(--radius-sm)",
        background: active ? "var(--brand)" : "var(--canvas-elevated)",
        color: active ? "#fff" : "var(--body)",
      }}
    >
      {children}
    </button>
  );
}

function Field({ label, children }) {
  return (
    <div className="text-sm">
      <span
        className="block mb-1.5"
        style={{ color: "var(--mute)", fontSize: 11, fontFamily: "var(--font-mono)", letterSpacing: "0.06em", textTransform: "uppercase" }}
      >
        {label}
      </span>
      <div className="flex gap-2 flex-wrap">{children}</div>
    </div>
  );
}

const DOMAIN_DOTS = { 인구: "인구", 수급: "수급", 재해: "재해" };

export default function TabI({ address }) {
  const [useType, setUseType] = useState("주거");
  const [resolution, setResolution] = useState("시군구");
  const [radius, setRadius] = useState(1000);
  const [synth, setSynth] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  async function run() {
    if (!address.trim()) return setError({ message: "주소를 먼저 입력하세요." });
    setLoading(true);
    setError(null);
    setData(null);
    try {
      setData(await board(address, useType, radius, resolution, synth));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <p className="text-sm mb-4" style={{ color: "var(--mute)" }}>
        인구·수급·재해·대지·생활맥락을 한 번에 모아 <span style={{ color: "var(--ink)", fontWeight: 500 }}>이 필지가 어떤 곳인지</span> 읽어드립니다.
        도메인 횡단 시사점은 모두 <span style={{ color: "var(--warn)", fontWeight: 500 }}>참고</span> — 최종 판단은 사람이. 종합점수·순위는 매기지 않습니다.
      </p>

      <div className="space-y-3">
        <Field label="건물 용도">
          {USE_TYPES.map((u) => (
            <ToggleBtn key={u} active={useType === u} onClick={() => setUseType(u)}>{u}</ToggleBtn>
          ))}
        </Field>
        <Field label="반경 (m)">
          {RADII.map((r) => (
            <ToggleBtn key={r} active={radius === r} onClick={() => setRadius(r)}>{r}</ToggleBtn>
          ))}
        </Field>
        <Field label="인구/수요 단위">
          {RESOLUTIONS.map((r) => (
            <ToggleBtn
              key={r}
              active={resolution === r}
              onClick={() => setResolution(r)}
              title="읍면동: 인구지표를 행정동 단위로. 반경: 반경 내 실인구(SGIS 집계구). 미지원 지표는 시군구 폴백"
            >
              {RES_LABEL[r]}
            </ToggleBtn>
          ))}
        </Field>
        <label className="flex items-center gap-2 text-sm cursor-pointer mt-1" style={{ color: "var(--body)" }}>
          <input type="checkbox" checked={synth} onChange={(e) => setSynth(e.target.checked)} />
          <span>AI 종합 해석 생성 <span style={{ color: "var(--mute)" }}>(①사실 해석 + ②AI 의견 — Claude 2콜, 느려짐)</span></span>
        </label>
      </div>

      <button
        onClick={run}
        disabled={loading}
        className="mt-5 px-4 py-2 font-medium disabled:opacity-50"
        style={{ background: "var(--brand)", color: "#fff", borderRadius: "var(--radius-sm)" }}
      >
        종합 읽기
      </button>

      {loading && <Spinner label="인구·수급·재해·대지·생활맥락 동시 수집 중… (여러 소스 병렬)" />}
      <div className="mt-4"><ErrorBox error={error} /></div>

      {data && (
        <div className="mt-5 space-y-6">
          {/* 헤더 */}
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="blue">{data.site.sigungu || data.site.address}</Badge>
            <Badge>{data.use_type}</Badge>
            <Badge>반경 {data.radius}m</Badge>
            {data.region && <Badge>{data.region.name}</Badge>}
            <Badge>기준일 {data.base_date}</Badge>
          </div>

          {/* ★ S4 종합 산출 — 벽으로 분리된 두 블록 (사실 vs AI 의견) */}
          {data.synthesis && (
            <section className="space-y-3">
              {/* ① 사실 종합 (해석) — 그라운디드 */}
              <div
                className="p-4"
                style={{ border: "1px solid var(--hairline)", borderRadius: "var(--radius)", borderLeft: "3px solid var(--ok)" }}
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-sm font-semibold" style={{ color: "var(--ink)" }}>① 사실 종합</span>
                  <Badge tone="green">검증된 사실 · 참고</Badge>
                  {data.synthesis.interpretation_source !== "ai" && (
                    <Badge tone="slate">{data.synthesis.interpretation_source === "no_data" ? "확인 불가" : "규칙 폴백"}</Badge>
                  )}
                  {data.synthesis.interpretation_model && <Badge tone="slate">{data.synthesis.interpretation_model}</Badge>}
                </div>
                <p className="text-sm whitespace-pre-line" style={{ color: "var(--body)", lineHeight: 1.6 }}>
                  {data.synthesis.interpretation}
                </p>
              </div>

              {/* 벽 — ②는 AI 의견임을 명확히 라벨 */}
              <div
                className="p-4"
                style={{ border: "1px solid var(--warn)", borderRadius: "var(--radius)", background: "var(--canvas-elevated)" }}
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-sm font-semibold" style={{ color: "var(--ink)" }}>② AI 판단</span>
                  <Badge tone="amber">AI 의견 · 검증 보장 없음</Badge>
                  {data.synthesis.judgment_source !== "ai" && (
                    <Badge tone="slate">{data.synthesis.judgment_source === "no_data" ? "확인 불가" : "판단 유보"}</Badge>
                  )}
                  {data.synthesis.judgment_model && <Badge tone="slate">{data.synthesis.judgment_model}</Badge>}
                </div>
                <p className="text-xs mb-2" style={{ color: "var(--warn)" }}>⚠ {data.synthesis.judgment_label}</p>
                <p className="text-sm whitespace-pre-line" style={{ color: "var(--body)", lineHeight: 1.6 }}>
                  {data.synthesis.judgment}
                </p>
              </div>
            </section>
          )}

          {/* 도메인 커버리지 — no silent skip */}
          <section>
            <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--body)" }}>도메인 확보 현황</h3>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {data.coverage.map((c, i) => (
                <div
                  key={i}
                  className="px-3 py-2"
                  style={{
                    border: "1px solid var(--hairline)",
                    borderRadius: "var(--radius-sm)",
                    borderLeft: `3px solid ${c.available ? "var(--ok)" : "var(--warn)"}`,
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold" style={{ color: "var(--body)" }}>{c.domain}</span>
                    <span style={{ color: c.available ? "var(--ok)" : "var(--warn)", fontSize: 11 }}>
                      {c.available ? "확보" : "확인 불가"}
                    </span>
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--mute)" }}>{c.detail}</div>
                </div>
              ))}
            </div>
          </section>

          {/* ★ S2 교차 시사점 — 도메인 횡단 '참고' */}
          <section>
            <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--body)" }}>
              교차 시사점 <span style={{ color: "var(--mute)", fontWeight: 400 }}>· 도메인 횡단 (참고)</span>
            </h3>
            {data.cross_implications.length === 0 ? (
              <p className="text-sm px-3 py-2" style={{ color: "var(--mute)", border: "1px dashed var(--hairline)", borderRadius: "var(--radius-sm)" }}>
                이 필지에서 발화한 교차 규칙이 없습니다 (조건 미충족 또는 확인 불가).
              </p>
            ) : (
              <div className="space-y-2">
                {data.cross_implications.map((c, i) => (
                  <div
                    key={i}
                    className="p-3"
                    style={{ border: "1px solid var(--hairline)", borderRadius: "var(--radius)", borderLeft: "3px solid var(--warn)" }}
                  >
                    <div className="flex items-center gap-1.5 flex-wrap mb-1">
                      <span className="text-sm font-semibold" style={{ color: "var(--ink)" }}>{c.name}</span>
                      {c.domains.map((d, j) => (
                        <Badge key={j} tone="slate">{DOMAIN_DOTS[d] || d}</Badge>
                      ))}
                      <Badge tone="amber">{c.tag}</Badge>
                    </div>
                    <p className="text-sm" style={{ color: "var(--body)" }}>{c.text}</p>
                    <div className="mt-1.5 flex flex-col gap-0.5">
                      {c.basis.map((b, j) => (
                        <span key={j} className="text-xs flex items-center gap-1.5 flex-wrap" style={{ color: "var(--mute)" }}>
                          <span>{b.key}: <span style={{ color: "var(--body)" }}>{b.detail}</span></span>
                          <ProximityChip level={b.proximity} />
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* 단일 지표 함의 (implications.json) */}
          {data.implications.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--body)" }}>단일 지표 함의</h3>
              <ul className="space-y-1">
                {data.implications.map((im, i) => (
                  <li key={i} className="text-sm flex items-start gap-2" style={{ color: "var(--body)" }}>
                    <Badge tone="amber">{im.tag}</Badge>
                    <span>{im.text} <span style={{ color: "var(--mute)" }}>({im.basis})</span></span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 수급진단 요약 */}
          {data.diagnoses.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--body)" }}>수급진단</h3>
              <div className="flex flex-wrap gap-2">
                {data.diagnoses.map((d, i) => (
                  <span key={i} className="text-xs px-2.5 py-1" style={{ border: "1px solid var(--hairline)", borderRadius: "var(--radius-sm)" }}>
                    <span style={{ color: "var(--body)" }}>{d.name}</span>{" "}
                    <span style={{ color: d.supply.level === "적음" ? "var(--warn)" : d.supply.level === "많음" ? "var(--ok)" : "var(--mute)" }}>
                      수요 {d.demand.level}·공급 {d.supply.level}
                    </span>
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* 대지 정보 */}
          {(data.land_price?.price_per_sqm != null || data.building?.name) && (
            <section>
              <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--body)" }}>대지 <span style={{ color: "var(--mute)", fontWeight: 400 }}>· 필지</span></h3>
              <div className="text-sm space-y-0.5" style={{ color: "var(--body)" }}>
                {data.land_price?.price_per_sqm != null && (
                  <div>개별공시지가 <span className="font-semibold" style={{ color: "var(--ink)" }}>{data.land_price.price_per_sqm.toLocaleString("ko-KR")}원/㎡</span>
                    {data.land_price.year && <span style={{ color: "var(--mute)" }}> ({data.land_price.year})</span>}
                    {" "}<ProximityChip level="대지" />
                  </div>
                )}
                {data.building?.name && (
                  <div>{data.building.name}
                    {data.building.far != null && <span style={{ color: "var(--mute)" }}> · 용적률 {data.building.far}%</span>}
                    {data.building.bcr != null && <span style={{ color: "var(--mute)" }}> · 건폐율 {data.building.bcr}%</span>}
                  </div>
                )}
              </div>
            </section>
          )}

          <Notes notes={data.notes} />
        </div>
      )}
    </div>
  );
}
