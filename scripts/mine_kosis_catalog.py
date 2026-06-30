"""Phase 1 — KOSIS 카탈로그 마이너 (docs/KOSIS_DEPTH_PLAN.md).

KOSIS 주제 트리(statisticsList.do)를 재귀 크롤해 통계표를 전수 발굴하고,
'시군구' 해석 가능 후보를 추려 out/kosis_catalog.json 에 적재한다.

경쟁사가 수작업으로 찾은 통계표 풀을 공공 API 로 자동 재구축 (카피 아님, 절대 원칙 1).
읽기 전용 — 기존 기능 무영향. KOSIS 분당 호출 제한 대응으로 호출 사이 슬립.

사용:
    python scripts/mine_kosis_catalog.py                 # 전체 주제 크롤
    python scripts/mine_kosis_catalog.py --topics A,I1   # 인구·주거만 (빠른 시범)
    python scripts/mine_kosis_catalog.py --delay 0.5     # 호출 간 슬립(초)

산출(out/kosis_catalog.json):
    {crawled_at, topics, stats{folders,tables,sigungu_tables}, sigungu[...], all_tables[...]}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

# 프로젝트 루트 기준 경로 (scripts/ 의 부모)
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"

_URL = "https://kosis.kr/openapi/statisticsList.do"
# 시군구 해석 가능성 판별 키워드 (표 이름 기준 1차 필터)
_SIGUNGU_HINTS = ("시군구", "행정구역", "시도/시군구", "시·군·구")


def _key() -> str:
    load_dotenv()
    k = os.getenv("KOSIS_KEY")
    if not k:
        sys.exit("KOSIS_KEY 미설정 (.env 확인)")
    return k


def _fetch_list(client: httpx.Client, key: str, parent: str | None) -> list:
    """주제/표 1단계 목록. 폴더면 하위 노드들, 리프 부모면 표들. 실패 시 빈 리스트."""
    params = {
        "method": "getList",
        "apiKey": key,
        "format": "json",
        "jsonVD": "Y",
        "vwCd": "MT_ZTITLE",  # 주제별 보기
    }
    if parent:
        params["parentListId"] = parent
    try:
        r = client.get(_URL, params=params, timeout=20.0)
        r.raise_for_status()
        j = r.json()
        return j if isinstance(j, list) else []
    except Exception as e:  # noqa: BLE001 — 한 노드 실패가 전체 크롤을 막지 않게
        print(f"    ! {parent or 'ROOT'} 조회 실패: {type(e).__name__}", file=sys.stderr)
        return []


def _is_sigungu(tbl_nm: str) -> bool:
    return any(h in tbl_nm for h in _SIGUNGU_HINTS)


def mine(topics: list[str] | None, delay: float) -> dict:
    """주제 트리 BFS 크롤 → 표 수집. topics 지정 시 해당 최상위만."""
    key = _key()
    client = httpx.Client(timeout=20.0)

    folders = 0
    tables: dict[str, dict] = {}  # tbl_id → 표 (dedup)
    # 큐 항목: (parent_list_id 또는 None, 주제경로[])
    queue: deque = deque()
    queue.append((None, []))  # ROOT
    visited: set = set()
    steps = 0

    try:
        while queue:
            parent, path = queue.popleft()
            rows = _fetch_list(client, key, parent)
            time.sleep(delay)
            steps += 1
            for row in rows:
                list_id = row.get("LIST_ID")
                tbl_id = row.get("TBL_ID")
                nm = (row.get("LIST_NM") or row.get("TBL_NM") or "").strip()
                if tbl_id:
                    # 실제 통계표 (리프)
                    if tbl_id not in tables:
                        tables[tbl_id] = {
                            "org_id": row.get("ORG_ID"),
                            "tbl_id": tbl_id,
                            "tbl_nm": (row.get("TBL_NM") or "").strip(),
                            "topic_path": " > ".join(path),
                            "sigungu": _is_sigungu(row.get("TBL_NM") or ""),
                        }
                elif list_id and list_id not in visited:
                    # 하위 주제 폴더 → 재귀
                    visited.add(list_id)
                    folders += 1
                    # ROOT 단계에서 topics 필터 (최상위 주제 한정)
                    if parent is None and topics and list_id not in topics:
                        continue
                    queue.append((list_id, path + [nm]))
            if steps % 20 == 0 or not queue:  # 로그 스팸 방지 — 20스텝마다 1회
                # flush=True: 파일 리다이렉트 시에도 진행상황 즉시 보이게 (버퍼링 방지)
                print(f"  크롤 중… 폴더 {folders} · 표 {len(tables)} (큐 {len(queue)})", flush=True)
    finally:
        client.close()

    print()  # 진행줄 마무리
    all_tables = list(tables.values())
    sigungu = [t for t in all_tables if t["sigungu"]]
    return {
        "crawled_at": datetime.now().isoformat(timespec="seconds"),
        "topics": topics or "ALL",
        "stats": {
            "folders": folders,
            "tables": len(all_tables),
            "sigungu_tables": len(sigungu),
        },
        "sigungu": sorted(sigungu, key=lambda t: (t["org_id"] or "", t["tbl_id"])),
        "all_tables": sorted(all_tables, key=lambda t: (t["org_id"] or "", t["tbl_id"])),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="KOSIS 카탈로그 마이너 (Phase 1)")
    ap.add_argument("--topics", default="", help="최상위 주제 ID 콤마구분 (예: A,I1). 비우면 전체")
    ap.add_argument("--delay", type=float, default=0.3, help="호출 간 슬립(초, 분당제한 대응)")
    ap.add_argument("--out", default=str(OUT_DIR / "kosis_catalog.json"))
    args = ap.parse_args()

    topics = [t.strip() for t in args.topics.split(",") if t.strip()] or None
    print(f"KOSIS 카탈로그 크롤 시작 (topics={topics or 'ALL'}, delay={args.delay}s)")
    result = mine(topics, args.delay)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    s = result["stats"]
    print(f"\n완료 → {out_path}")
    print(f"  주제 폴더 {s['folders']} · 통계표 {s['tables']} · 시군구 후보 {s['sigungu_tables']}")
    # 시군구 후보 상위 10 미리보기
    print("\n시군구 후보 표 (앞 10):")
    for t in result["sigungu"][:10]:
        print(f"  [{t['org_id']}] {t['tbl_id']}  {t['tbl_nm']}")


if __name__ == "__main__":
    main()
