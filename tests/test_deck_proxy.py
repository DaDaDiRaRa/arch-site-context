"""deck-builder 패스스루 프록시 테스트 (네트워크 없음, httpx.AsyncClient monkeypatch).

핵심: 백엔드가 프론트를 서빙할 때 POST /deck/kdbm 이 SPA 정적마운트(405)에 걸리지 않고
프록시 라우트로 가는지 + deck-builder 미기동 시 graceful 502.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class _FakeResp:
    def __init__(self, content=b"PPTXDATA", status=200):
        self.content = content
        self.status_code = status
        self.headers = {
            "content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "content-disposition": 'attachment; filename="site_deck.pptx"',
        }


class _FakeClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, content=None, headers=None):
        return _FakeResp()


def test_deck_proxy_passthrough(monkeypatch) -> None:
    monkeypatch.setattr("app.routers.deck_proxy.httpx.AsyncClient", _FakeClient)
    r = client.post("/deck/full", json={"address": "서울 영등포구 여의대로 24", "use_type": "주거"})
    assert r.status_code == 200  # 405 아님 — 라우트가 정적마운트보다 먼저 잡힘
    assert r.content == b"PPTXDATA"
    assert "presentationml" in r.headers.get("content-type", "")


def test_deck_proxy_graceful_when_down(monkeypatch) -> None:
    class _Boom(_FakeClient):
        async def post(self, *a, **k):
            raise ConnectionError("connection refused")

    monkeypatch.setattr("app.routers.deck_proxy.httpx.AsyncClient", _Boom)
    r = client.post("/deck/full", json={"address": "x"})
    assert r.status_code == 502
    assert "deck-builder" in r.json()["detail"]
