"""kordoc CLI 래퍼 테스트 (§8.15 HWP 내보내기) — services/kordoc_client.py.

에러 경로(빈 마크다운·CLI 못 찾음·node 없음·빌드 안 됨)는 kordoc 설치 여부와 무관하게
항상 돈다 — 그게 실제로 실패하는 조건이라서. CLI 를 실제로 부르는 검사(생성 왕복)만
kordoc 이 설치돼 있을 때만(live, skipif) — concept-studio 의 kordoc_client 스모크
패턴(docs/adr/001-kordoc-integration.md)을 그대로 따른다.
"""

from __future__ import annotations

import pytest

from app.services import kordoc_client as kc

live = pytest.mark.skipif(
    not kc.available(),
    reason="kordoc 이 설치돼 있지 않음 — KORDOC_CLI 미설정 (§8.15, 로컬 전용 기능)",
)


# ── 에러 경로 — 설치 여부 무관 ────────────────────────────────────────────────


def test_empty_markdown_is_refused() -> None:
    with pytest.raises(kc.KordocError, match="빈 마크다운"):
        kc.markdown_to_hwpx("   ")


def test_cli_not_found_raises(monkeypatch) -> None:
    monkeypatch.setenv("KORDOC_CLI", "definitely-not-a-real-binary-xyz")
    assert kc.available() is False
    with pytest.raises(kc.KordocError, match="찾을 수 없음"):
        kc.markdown_to_hwpx("# 제목")


def test_js_path_without_node_raises(monkeypatch) -> None:
    monkeypatch.setenv("KORDOC_CLI", "D:/nope/dist/cli.js")
    monkeypatch.setattr(kc.shutil, "which", lambda name: None if name == "node" else "/usr/bin/x")
    assert kc.available() is False
    with pytest.raises(kc.KordocError, match="node"):
        kc.markdown_to_hwpx("# 제목")


def test_js_path_missing_build_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("KORDOC_CLI", str(tmp_path / "not_built.js"))
    monkeypatch.setattr(kc.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else None)
    with pytest.raises(kc.KordocError, match="빌드되지 않음"):
        kc.markdown_to_hwpx("# 제목")


def test_generate_failure_raises(monkeypatch) -> None:
    """CLI 는 찾았지만 subprocess 가 0이 아닌 코드로 죽는 경우 — stderr 를 실어 올린다."""
    monkeypatch.setenv("KORDOC_CLI", "kordoc-stub")
    monkeypatch.setattr(kc.shutil, "which", lambda name: "/usr/bin/kordoc-stub" if name == "kordoc-stub" else None)

    class _Proc:
        returncode = 1
        stdout = b""
        stderr = b"boom"

    monkeypatch.setattr(kc.subprocess, "run", lambda *a, **k: _Proc())
    with pytest.raises(kc.KordocError, match="generate 실패"):
        kc.markdown_to_hwpx("# 제목")


# ── 실제 CLI 왕복 (설치돼 있을 때만) ──────────────────────────────────────────


@live
def test_version_is_the_one_we_tested() -> None:
    v = kc.version()
    major = v.split(".")[0]
    assert major == kc.TESTED_VERSION.split(".")[0], (
        f"kordoc 메이저 버전이 바뀜: {v} (검증한 버전 {kc.TESTED_VERSION}) — generate 출력을 다시 확인"
    )


@live
def test_markdown_to_hwpx_produces_a_zip() -> None:
    """HWPX 는 OPC(zip) 컨테이너 — PK 매직바이트로 최소 검증(내용 파싱은 kordoc 몫)."""
    data = kc.markdown_to_hwpx("# 제목\n\n1. 첫째\n2. 둘째\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n")
    assert data[:2] == b"PK"
    assert len(data) > 1000
