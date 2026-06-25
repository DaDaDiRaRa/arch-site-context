"""arch-site-context (터읽기) — FastAPI 진입점.

P0: 골격 + 스키마 스텁. 모든 엔드포인트는 하드코딩 샘플 JSON을 200으로 반환한다.
실제 API 호출·계산은 P1 이후. (CLAUDE.md 7장 로드맵)
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import analyze, facilities, health, matrix

load_dotenv()  # .env 로드 (키는 다음 Phase부터 사용)

# 합성 PNG 저장·서빙 경로 (out/). 없으면 생성.
_OUT_DIR = Path(__file__).resolve().parent.parent / "out"
_OUT_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="arch-site-context (터읽기)",
    description="대지 주소로 동네를 읽어주는 대지 분석 보조 — 모드 A(지역 통계)·모드 B(주변 시설).",
    version="0.0.1-P0",
)

# 프론트(React+Vite) 로컬 개발용. 배포 시 도메인 제한 예정.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(facilities.router)
app.include_router(analyze.router)
app.include_router(matrix.router)

# 합성된 위성 PNG 다운로드/표시용 정적 서빙 (예: /files/maps/map_xxx.png)
app.mount("/files", StaticFiles(directory=str(_OUT_DIR)), name="files")


@app.get("/")
def root() -> dict:
    """루트 안내."""
    return {
        "service": "arch-site-context",
        "team": "터읽기",
        "phase": "P0",
        "docs": "/docs",
        "endpoints": ["/health", "/facilities", "/facilities/map", "/analyze", "/matrix"],
    }
