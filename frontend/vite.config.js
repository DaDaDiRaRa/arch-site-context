import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// 백엔드(FastAPI) 주소. 환경변수로 덮어쓰기 가능.
const API = process.env.VITE_API_TARGET || "http://127.0.0.1:8000";

// 개발 서버에서 백엔드 엔드포인트를 프록시 → CORS·URL 고민 없이 상대경로로 호출.
// /deck(대지분석 덱)도 이제 터읽기 백엔드가 직접 서빙(deck-builder 흡수).
const proxy = Object.fromEntries(
  ["/analyze", "/facilities", "/diagnose", "/compare", "/ask", "/site", "/seed", "/readout", "/board", "/deck", "/matrix", "/use-types", "/files", "/health"].map((p) => [
    p,
    { target: API, changeOrigin: true },
  ])
);

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy },
});
