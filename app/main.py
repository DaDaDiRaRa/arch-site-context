"""arch-site-context (터읽기) — FastAPI 진입점.

모드 A(지역 통계)·모드 B(주변 시설) 백엔드 + 빌드된 프론트 정적 서빙(단일 서비스).
"""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import FRONTEND_DIST, OUT_DIR
from app.routers import (
    analyze, ask, board, compare, context_pack, deck, diagnose, facilities, health,
    history, matrix, readout, seed, site, surroundings,
)

load_dotenv()  # 로컬 .env 로드 (배포는 Secret Manager → env 주입)

# 합성 PNG 저장·서빙 경로. Cloud Run 은 OUT_DIR=/tmp/out 등 쓰기 가능 경로 지정.
OUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="arch-site-context (터읽기)",
    description="대지 주소로 동네를 읽어주는 대지 분석 보조 — 모드 A(지역 통계)·모드 B(주변 시설).",
    version="1.0.0",
)

# 단일 서비스(프론트 정적 서빙)면 CORS 불필요하나, 별도 호스팅 대비 허용 유지.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api")
def api_info() -> dict:
    """서비스 안내 (루트 / 는 프론트가 차지)."""
    return {
        "service": "arch-site-context",
        "team": "터읽기",
        "docs": "/docs",
        "endpoints": ["/health", "/facilities", "/facilities/map", "/analyze", "/matrix", "/diagnose", "/compare", "/ask", "/site", "/seed", "/readout", "/board", "/context-pack", "/context-pack/pptx", "/surroundings", "/surroundings/pptx"],
    }


app.include_router(health.router)
app.include_router(facilities.router)
app.include_router(analyze.router)
app.include_router(matrix.router)
app.include_router(diagnose.router)
app.include_router(compare.router)
app.include_router(ask.router)
app.include_router(site.router)
app.include_router(seed.router)
app.include_router(readout.router)
app.include_router(board.router)
app.include_router(context_pack.router)
app.include_router(surroundings.router)
app.include_router(deck.router)  # /deck/full 대지분석 덱 (deck-builder 흡수 — 정적마운트보다 먼저)
app.include_router(history.router)  # /history 생성물 이력 (재다운로드)

# 합성된 위성 PNG 다운로드/표시용 정적 서빙 (예: /files/maps/map_xxx.png)
app.mount("/files", StaticFiles(directory=str(OUT_DIR)), name="files")

# 빌드된 프론트가 있으면 루트에 정적 서빙(SPA). 반드시 마지막에 마운트(catch-all).
# 로컬 개발은 Vite(5173) 사용 — dist 없으면 / 는 비활성.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
