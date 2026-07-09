#!/usr/bin/env python3
"""터읽기 MCP 서버 (T 시리즈 3단계).

기존 서비스(build_board·build_diagnosis)를 얇게 래핑해 Claude·에이전트가 개별로도, 파이프라인
으로도 대지 인문·생활맥락을 쓰게 한다. 로직 변경 시 도구에 자동 반영(서비스 직접 import).

## Claude Code에 연결
  claude mcp add teoilgi python d:/APPS/arch-site-context/mcp_server/server.py

## 노출 도구
- read_site_context : 주소 → 대지 종합 읽기 압축본(board_brief) — 인구지수·수급·재해·교차·설계드라이버(·종합)
- diagnose_supply   : 주소 → 수급진단(인구수요 × 시설공급 교차)만 (경량)

원칙 그대로: 실제 API·출처 명시·확인불가는 정직·판단은 사람. 새 숫자 안 만듦.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_ROOT / ".env")

from fastapi.responses import JSONResponse  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("teoilgi")


def _err(resp: JSONResponse) -> str:
    try:
        body = json.loads(bytes(resp.body).decode())
    except Exception:  # noqa: BLE001
        body = {"message": "확인 불가"}
    return json.dumps({"error": body.get("code", "ERROR"),
                       "message": body.get("message", "확인 불가")}, ensure_ascii=False)


@mcp.tool()
def read_site_context(
    address: str,
    use_type: str = "주거",
    radius: int = 1000,
    resolution: str = "시군구",
    synthesize: bool = False,
) -> str:
    """대지 주소 → 그 대지의 인문·생활맥락 종합 읽기(압축본).

    포함: 인구통계(전국=100 지수·근접도), 수급진단(인구수요×시설공급), 재해위험(홍수·산사태·폭염),
    도메인 횡단 교차시사점, ★지배 설계 드라이버 2~3개, 도메인 확보현황. 대지·시설 정보 요약.
    synthesize=true 면 사실 종합(①)·AI 판단(②) 두 블록도 생성(느려짐, Claude 2콜).

    use_type: 주거|상업|의료 등(matrix). resolution: 시군구|읍면동|반경.
    데이터로 확인 불가한 부분은 정직하게 비움 — 추정하지 않음.
    """
    from app.routers.board import board
    from app.schemas.board import BoardRequest

    r = board(BoardRequest(address=address, use_type=use_type, radius=radius,
                           resolution=resolution, synthesize=synthesize, brief=True))
    if isinstance(r, JSONResponse):
        return _err(r)
    return json.dumps(r, ensure_ascii=False, indent=2)  # brief=True → 이미 dict


@mcp.tool()
def diagnose_supply(address: str, radius: int = 1000, resolution: str = "시군구") -> str:
    """대지 주소 → 수급진단(인구 수요 × 반경 내 시설 공급 교차)만 경량 반환.

    "이 동네 무엇이 부족/과잉인가"를 근거와 함께. 부족/과잉은 휴리스틱이라 모두 '참고'.
    resolution='반경'이면 SGIS 집계구 실인구로 수요·공급 같은 반경 (더 정밀·느림).
    """
    from app.services.diagnose import build_diagnosis
    from app.services.kakao import KakaoError

    try:
        res = build_diagnosis(address, radius=radius, resolution=resolution)
    except KakaoError as e:
        return json.dumps({"error": "ADDR_UNRESOLVED", "message": f"주소 해석 불가: {e}"}, ensure_ascii=False)
    return res.model_dump_json(indent=2)


if __name__ == "__main__":
    mcp.run()
