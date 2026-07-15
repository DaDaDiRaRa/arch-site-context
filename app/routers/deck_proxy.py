"""deck-builder(:8100) 패스스루 프록시 — 프론트 TabL(대지분석 덱) 연결.

vite dev(:5173)는 자체 프록시(/deck→:8100)를 쓰지만, 백엔드가 프론트를 서빙(배포·uvicorn)하면
`POST /deck/full` 이 SPA 정적마운트(GET/HEAD 전용)에 걸려 **405 Method Not Allowed** 가 난다.
이 얇은 패스스루가 요청을 deck-builder 로 전달한다(정적마운트보다 먼저 등록되어야 함).

터읽기 분석 로직과 무관한 **프론트 연동용 패스스루** — deck-builder 미기동/미배포면 graceful 502.
대상은 `DECK_TARGET`(env, 기본 로컬 :8100). Cloud Run 은 deck-builder 배포 + DECK_TARGET 설정 시 작동.
"""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

router = APIRouter(tags=["deck"])


def _target() -> str:
    return os.getenv("DECK_TARGET", "http://127.0.0.1:8100").rstrip("/")


@router.post("/deck/full")
async def deck_full(req: Request):
    """대지분석 덱 생성 요청을 deck-builder 로 그대로 전달하고 pptx 를 스트리밍 반환."""
    body = await req.body()
    url = f"{_target()}/deck/full"
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(
                url, content=body,
                headers={"Content-Type": req.headers.get("content-type", "application/json")},
            )
    except Exception as e:  # noqa: BLE001 — 연결 실패는 명확한 502 로 안내 (절대 원칙 3)
        return JSONResponse(status_code=502, content={
            "detail": (
                f"deck-builder 서비스에 연결할 수 없습니다 ({_target()}). "
                f"로컬은 deck-builder(:8100) 기동, 배포는 DECK_TARGET 설정이 필요합니다. "
                f"({type(e).__name__})"
            )
        })
    return Response(
        content=r.content,
        status_code=r.status_code,
        media_type=r.headers.get("content-type", "application/octet-stream"),
        headers={
            "Content-Disposition": r.headers.get(
                "content-disposition", 'attachment; filename="site_deck.pptx"'
            )
        },
    )
