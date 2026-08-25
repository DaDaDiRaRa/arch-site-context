"""kordoc CLI 래퍼 — 마크다운 → HWPX (§8.15 HWP 내보내기).

kordoc(D:\\APPS\\kordoc, npm/TypeScript)은 이 Python 프로세스 안에서 못 돈다.
연동 방식은 형제앱 concept-studio 가 이미 실측 검증한 **CLI subprocess**
(concept-studio docs/adr/001-kordoc-integration.md) — 새로 조사하지 않고 그대로 따른다.

concept-studio 의 kordoc_client.py 는 파싱 방향(HWP→구조화, `parse`)까지 감싸지만,
우리는 그 반대 — 생성 방향(마크다운→HWPX, `markdownToHwpx`)만 쓴다. `kordoc generate`
서브커맨드가 그 CLI 진입점이다. 실패는 예외로 올린다 — 조용히 빈 파일을 돌려주지 않는다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List

#: 검증한 kordoc 버전 (concept-studio 실측·TESTED_VERSION 과 동일 메이저).
TESTED_VERSION = "3.4.1"

#: 공문서 프리셋 — 기안문(official)|보고서(report)|계획서(plan)|통지(notice)|회의록(minutes)
DEFAULT_PRESET = "report"


class KordocError(RuntimeError):
    """HWPX 생성 실패. 호출자는 그래스풀 폴백(예: PPTX만 제공)으로 흡수한다."""


def _resolve_cli() -> List[str]:
    """실행 방법 — PATH 의 `kordoc`, 또는 `node <경로>/dist/cli.js` (KORDOC_CLI 환경변수)."""
    cli = os.getenv("KORDOC_CLI", "kordoc")
    if cli.endswith(".js"):
        node = shutil.which("node")
        if not node:
            raise KordocError("node 를 찾을 수 없음 — KORDOC_CLI 가 .js 인데 Node.js 미설치")
        if not Path(cli).exists():
            raise KordocError(f"kordoc 이 빌드되지 않음: {cli} (kordoc 레포에서 npm ci && npm run build)")
        return [node, cli]
    found = shutil.which(cli)
    if not found:
        raise KordocError(
            f"kordoc 실행파일을 찾을 수 없음: {cli!r}. "
            "KORDOC_CLI 에 dist/cli.js 절대경로를 넣거나 `npm i -g kordoc` 설치"
        )
    return [found]


def available() -> bool:
    """설치 여부 — 라우터가 HWP 옵션 노출 전 확인·테스트가 skip 판단에 쓴다."""
    try:
        _resolve_cli()
        return True
    except KordocError:
        return False


def version() -> str:
    """설치된 kordoc 버전. TESTED_VERSION 과 메이저가 다르면 `generate` 출력이 바뀌었을 수 있다."""
    proc = subprocess.run([*_resolve_cli(), "--version"], capture_output=True, timeout=30)
    return proc.stdout.decode("utf-8", errors="replace").strip()


def markdown_to_hwpx(markdown: str, *, preset: str = DEFAULT_PRESET, timeout_sec: int = 60) -> bytes:
    """마크다운 → 공문서 표준서식 HWPX 바이트 (`kordoc generate`, markdownToHwpx 래핑).

    stdin 으로 마크다운을 넣고(`-`), 임시파일에 쓰게 한 뒤 바이트로 읽어 돌려준다
    (CLI 가 바이너리를 stdout 으로 못 흘려서 -o 필수). 실패·시간초과는 KordocError.
    """
    if not markdown.strip():
        raise KordocError("빈 마크다운 — 변환할 내용 없음")
    cli = _resolve_cli()
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "out.hwpx"
        try:
            proc = subprocess.run(
                [*cli, "generate", "-", "-o", str(out_path), "--preset", preset, "--silent"],
                input=markdown.encode("utf-8"),
                capture_output=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise KordocError(f"kordoc 시간 초과({timeout_sec}s)") from exc
        if proc.returncode != 0 or not out_path.exists():
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            raise KordocError(f"kordoc generate 실패(코드 {proc.returncode}): {stderr[:400]}")
        return out_path.read_bytes()
