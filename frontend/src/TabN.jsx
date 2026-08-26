import { useState } from "react";
import { ErrorBox } from "./ui.jsx";

/** 컨셉 스튜디오 — **다른 앱**을 여기서 연다.
 *
 *  터읽기가 대지를 읽고, 컨셉 스튜디오가 그 위에 컨셉을 세운다. 두 일은 화면이 이어져야
 *  건축가가 주소를 두 번 안 친다 — 그래서 탭 하나로 붙였다.
 *
 *  **다른 탭들과 다르다.** 나머지는 우리 백엔드를 부르지만 이 탭은 남의 앱을 iframe 으로
 *  띄운다. 우리가 하는 일은 주소를 넘기는 것뿐이고, 근거 수집·컨셉·보고서는 전부 저쪽 일이다.
 *  (터읽기 코드 변경을 이 파일 + App.jsx 두 줄로 묶은 이유 — provider 경계를 안 흐리려고.)
 *
 *  주소는 `?address=` 로 넘어가 저쪽 「근거 모음」 화면의 주소 칸에 그대로 들어간다.
 */

//: 개발 기본값. 배포에서는 `VITE_CONCEPT_STUDIO_URL` 로 덮는다.
//: 이 앱과 **다른 포트**라 프록시를 안 탄다 — iframe 은 절대주소로 연다.
const BASE =
  import.meta.env.VITE_CONCEPT_STUDIO_URL || "http://localhost:5173";

export default function TabN({ address }) {
  const [opened, setOpened] = useState("");
  const [error, setError] = useState(null);

  const ready = address.trim().length > 0;
  const url = ready
    ? `${BASE}/?address=${encodeURIComponent(address.trim())}`
    : "";

  function open() {
    if (!ready) return setError({ message: "주소를 먼저 입력하세요." });
    setError(null);
    setOpened(url);
  }

  return (
    <div>
      <p style={{ color: "var(--body)", fontSize: 14, lineHeight: 1.7, marginBottom: 14 }}>
        대지 주소와 고시·가이드라인 문서로 <b>근거 모음</b>을 만들고, 그 위에서 컨셉 보고서를
        씁니다. <b>모든 수치가 출처를 인용</b>하고, 인용 없는 숫자가 있으면 보고서가 만들어지지
        않습니다.
      </p>
      <p style={{ color: "var(--mute)", fontSize: 12, lineHeight: 1.7, marginBottom: 16 }}>
        여기서 여는 것은 <b>별도 앱(컨셉 스튜디오)</b>입니다 — 터읽기가 대지를 읽고, 그쪽이
        컨셉을 세웁니다. 주소만 넘어가고 나머지 작업은 전부 그쪽에서 이뤄집니다.
      </p>

      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <button
          onClick={open}
          disabled={!ready}
          className="px-4 py-2 text-sm font-medium"
          style={{
            border: "1px solid var(--hairline)",
            borderRadius: "var(--radius-sm)",
            background: ready ? "var(--ink)" : "var(--canvas)",
            color: ready ? "var(--canvas)" : "var(--mute)",
            cursor: ready ? "pointer" : "not-allowed",
          }}
        >
          {opened ? "다시 열기" : "컨셉 스튜디오 열기"}
        </button>
        {ready && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-2 text-xs"
            style={{
              border: "1px solid var(--hairline)",
              borderRadius: "var(--radius-sm)",
              color: "var(--body)",
            }}
          >
            새 창으로 ↗
          </a>
        )}
        {ready && (
          <span style={{ color: "var(--mute)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
            {BASE}
          </span>
        )}
      </div>

      {error && <ErrorBox error={error} />}

      {opened ? (
        <iframe
          key={opened}
          src={opened}
          title="컨셉 스튜디오"
          style={{
            width: "100%",
            height: "78vh",
            minHeight: 620,
            border: "1px solid var(--hairline)",
            borderRadius: "var(--radius-sm)",
            background: "var(--canvas)",
          }}
        />
      ) : (
        <div
          style={{
            border: "1px dashed var(--hairline)",
            borderRadius: "var(--radius-sm)",
            padding: "42px 20px",
            textAlign: "center",
            color: "var(--mute)",
            fontSize: 13,
          }}
        >
          {ready
            ? "「컨셉 스튜디오 열기」를 누르면 여기에서 바로 씁니다."
            : "위에 대지 주소를 입력한 뒤 열어 주세요."}
        </div>
      )}

      {/* 안 뜨는 경우를 미리 말한다 — 다른 앱이라 이 화면의 오류창이 못 잡는다. */}
      {opened && (
        <p style={{ color: "var(--mute)", fontSize: 11, marginTop: 10, lineHeight: 1.6 }}>
          화면이 비어 있으면 컨셉 스튜디오가 안 떠 있는 것입니다({BASE}). 「새 창으로 ↗」로
          열어 보면 무엇이 잘못됐는지 그쪽 화면이 말해 줍니다.
        </p>
      )}
    </div>
  );
}
