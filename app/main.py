"""arch-site-context (터읽기) — FastAPI 진입점.

모드 A(지역 통계)·모드 B(주변 시설) 백엔드 + 빌드된 프론트 정적 서빙(단일 서비스).
"""

from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import PlainTextResponse

from app.config import FRONTEND_DIST, OUT_DIR
from app.routers import (
    analyze, ask, board, compare, context_pack, deck, diagnose, facilities, health,
    history, matrix, readout, seed, site, surroundings,
)

from mcp_server.server import mcp as _mcp

load_dotenv()  # 로컬 .env 로드 (배포는 Secret Manager → env 주입)

# 합성 PNG 저장·서빙 경로. Cloud Run 은 OUT_DIR=/tmp/out 등 쓰기 가능 경로 지정.
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- MCP (/mcp) --------------------------------------------------------------
# arch-site-model 배포에서 확립한 패턴 그대로(kunwon-ops docs/plan-mcp-gateway.md §9):
# lifespan 결합 · Bearer 토큰 미들웨어 · Mount 대신 raw ASGI 프리픽스 래퍼.
_mcp_asgi_app = _mcp.streamable_http_app()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    async with _mcp.session_manager.run():
        yield


# 나머지 REST API 는 지금처럼 공개로 둔다 — 여기서 막는 건 /mcp 뿐이다.
# 이 도구는 호출마다 ANTHROPIC_API_KEY(synthesize=true 시 Claude 2콜) + 정부 API 17종을
# 태우므로 공개로 열면 안 된다(판단 근거: kunwon-ops 저장소 docs/plan-mcp-gateway.md §7).
_MCP_SHARED_KEY = os.environ.get("ARCH_SITE_CONTEXT_MCP_KEY")


class _McpAuthMiddleware:
    """`/mcp` 전용 인증. Bearer 토큰이 ARCH_SITE_CONTEXT_MCP_KEY 와 일치해야 통과."""

    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        token = headers.get(b"authorization", b"").decode("latin-1")
        expected = f"Bearer {_MCP_SHARED_KEY}" if _MCP_SHARED_KEY else None
        # compare_digest — 토큰 비교 시간이 일치 길이에 따라 달라지지 않도록
        if not expected or not hmac.compare_digest(token, expected):
            resp = PlainTextResponse("Unauthorized", status_code=401)
            await resp(scope, receive, send)
            return
        await self._app(scope, receive, send)


class _McpMount:
    """"/mcp" 와 "/mcp/*" 를 FastMCP 로 보낸다. Starlette Mount 는 트레일링 슬래시
    없는 "/mcp" 자체를 못 잡아 캐치올(정적 파일 "/")로 새는 문제가 있다(실측:
    arch-site-model, kunwon-ops docs/plan-mcp-gateway.md §9). 그래서 라우팅 이전
    단계(순수 ASGI 래퍼)에서 프리픽스를 직접 잘라 우회한다."""

    def __init__(self, inner_app, mcp_app, prefix="/mcp"):
        self._app = inner_app
        self._mcp_app = mcp_app
        self._prefix = prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope["path"]
            if path == self._prefix or path.startswith(self._prefix + "/"):
                sub_scope = dict(scope)
                sub_scope["path"] = path[len(self._prefix):] or "/"
                await self._mcp_app(sub_scope, receive, send)
                return
        await self._app(scope, receive, send)


app = FastAPI(
    title="arch-site-context (터읽기)",
    description="대지 주소로 동네를 읽어주는 대지 분석 보조 — 모드 A(지역 통계)·모드 B(주변 시설).",
    version="1.0.0",
    lifespan=_lifespan,
)


# 단일 서비스(프론트 정적 서빙)면 CORS 불필요하나, 별도 호스팅 대비 허용 유지.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api")
def api_info(request: Request) -> dict:
    """서비스 안내 (루트 / 는 프론트가 차지).

    endpoints 는 **OpenAPI 스키마에서 생성**한다 — 손으로 적은 목록은 엔드포인트가 늘 때마다
    낡는다(실제로 board·deck·history·facilities/pptx 가 빠져 있었다). `app.routes` 를 직접
    훑지 않는 이유: include_router 한 라우터가 `_IncludedRouter` 로 중첩돼 들어가 평면 순회로는
    1개(`/api`)만 잡힌다(실측). 스키마는 FastAPI 가 첫 호출 후 캐시한다.
    `request.app` 은 이 FastAPI 인스턴스 — 모듈 전역 `app` 은 아래에서 MCP 래퍼로 재바인딩된다.
    """
    paths = sorted(request.app.openapi().get("paths", {}))
    return {
        "service": "arch-site-context",
        "team": "터읽기",
        "docs": "/docs",
        "endpoints": paths,
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

# uvicorn 은 "app.main:app" 심볼을 그대로 가져간다(Dockerfile CMD 참조). 이 래퍼는
# http 요청만 가로채고 lifespan/websocket 스코프는 그대로 넘겨서 위 _lifespan(=
# _mcp.session_manager.run())이 정상적으로 트리거된다.
app = _McpMount(app, _McpAuthMiddleware(_mcp_asgi_app))
