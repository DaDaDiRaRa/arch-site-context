"""GET /health — 헬스체크."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    """서비스 생존 확인."""
    return {"status": "ok", "service": "arch-site-context", "phase": "P0"}
