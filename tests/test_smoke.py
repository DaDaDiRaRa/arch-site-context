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
