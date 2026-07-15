import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// 백엔드(FastAPI) 주소. 환경변수로 덮어쓰기 가능.
const API = process.env.VITE_API_TARGET || "http://127.0.0.1:8000";
// deck-builder 서비스(KDBM 덱, B2 consumer). 별도 포트.
const DECK = process.env.VITE_DECK_TARGET || "http://127.0.0.1:8100";

// 개발 서버에서 백엔드 엔드포인트를 프록시 → CORS·URL 고민 없이 상대경로로 호출.
const proxy = Object.fromEntries(
  ["/analyze", "/facilities", "/diagnose", "/compare", "/ask", "/site", "/seed", "/readout", "/board", "/matrix", "/use-types", "/files", "/health"].map((p) => [
    p,
    { target: API, changeOrigin: true },
  ])
);
// /deck/* → deck-builder(:8100)
proxy["/deck"] = { target: DECK, changeOrigin: true };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy },
});
