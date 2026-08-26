"""P0 스모크 테스트 — 스텁이 200 + 샘플 JSON을 반환하는지 검증.

완료 기준: /health 와 /facilities 가 샘플 JSON 을 반환하면 통과.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_matrix_has_use_types() -> None:
    r = client.get("/matrix")
    assert r.status_code == 200
    assert "주거" in r.json()["use_types"]


def test_api_info_lists_every_endpoint() -> None:
    """`/api` 안내 목록은 손으로 적지 않고 OpenAPI 스키마에서 만든다 — 낡을 수 없도록.

    (예전엔 하드코딩이라 board·deck·history·facilities/pptx 가 빠져 있었다.)
    """
    r = client.get("/api")
    assert r.status_code == 200
    eps = r.json()["endpoints"]
    for path in ("/health", "/analyze", "/facilities", "/board", "/board/hwp",
                 "/deck/full", "/deck/svg", "/deck/dxf", "/deck/glb",
                 "/history", "/facilities/pptx", "/context-pack", "/surroundings"):
        assert path in eps, path
    assert eps == sorted(set(eps))
