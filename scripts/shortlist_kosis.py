"""Step 1 — KOSIS 건축관련 숏리스트 (docs/KOSIS_DEPTH_PLAN.md).

Phase 1 카탈로그(out/kosis_catalog.json)의 시군구 후보 중 **건축 대지분석 관련 14개 주제**만
골라, 각 표의 메타(getMeta)로 주기·최신연도·항목수·샘플항목을 일괄 추출 → 최신순 숏리스트.

region 해석 검증(다차원 표에서 false negative)은 여기서 안 함 — Step 1 목표는 "어떤 표를
편입 후보로 볼지" 추리는 것. region·objL 확정은 Phase 3(표별 수동).

읽기 전용. KOSIS 분당 제한 → 호출 사이 슬립. 오래 걸리면 백그라운드 실행 권장.

사용:
    python scripts/shortlist_kosis.py                 # 14개 건축주제 전체
    python scripts/shortlist_kosis.py --min-year 2018 # 2018년 이후 표만 ITM 조회(빠름)
산출(out/kosis_shortlist.json): 표별 {topic, prd_se, latest, item_count, sample_items[]}, 최신순.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
CATALOG = OUT_DIR / "kosis_catalog.json"
_META = "https://kosis.kr/openapi/statisticsData.do"

# 건축 대지분석 관련 14개 최상위 주제 (사용자 확정 2026-06-30). 농림·수산·광업·에너지·도소매·정부재정 제외.
ARCH_TOPICS = {
    "지역통계", "보건", "인구", "국토이용", "노동", "주거", "복지",
    "문화ㆍ여가", "환경", "교통ㆍ물류", "범죄ㆍ안전", "기업경영", "경제일반ㆍ경기", "사회일반",
}


def _key() -> str:
    load_dotenv()
    k = os.getenv("KOSIS_KEY")
    if not k:
        sys.exit("KOSIS_KEY 미설정 (.env 확인)")
    return k


def _meta(client: httpx.Client, key: str, org_id: str, tbl_id: str, type_: str) -> list:
    p = {"method": "getMeta", "apiKey": key, "format": "json", "jsonVD": "Y",
         "orgId": org_id, "tblId": tbl_id, "type": type_}
    try:
        r = client.get(_META, params=p, timeout=25.0)
        d = json.loads(r.text)
        return d if isinstance(d, list) else []
    except Exception:  # noqa: BLE001
        return []


def _year_of(latest: str | None) -> int:
    """'2026.05'·'2025'·'202605' → 연도 int. 파싱 불가 0."""
    if not latest:
        return 0
    digits = "".join(ch for ch in str(latest) if ch.isdigit())
    return int(digits[:4]) if len(digits) >= 4 else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="KOSIS 건축관련 숏리스트 (Step 1)")
    ap.add_argument("--delay", type=float, default=0.3, help="호출 간 슬립(초)")
    ap.add_argument("--min-year", type=int, default=0,
                    help="이 연도 미만 표는 ITM 조회 생략(PRD만, 빠름). 0=전부 ITM 조회")
    ap.add_argument("--limit", type=int, default=0, help="앞 N개만 (스모크 테스트용, 0=전체)")
    ap.add_argument("--out", default=str(OUT_DIR / "kosis_shortlist.json"))
    args = ap.parse_args()

    if not CATALOG.exists():
        sys.exit(f"{CATALOG} 없음 — 먼저 mine_kosis_catalog.py 실행")
    sig = json.loads(CATALOG.read_text(encoding="utf-8"))["sigungu"]

    def first(t: dict) -> str:
        return t["topic_path"].split(" > ")[0] if t["topic_path"] else ""

    cand = [t for t in sig if first(t) in ARCH_TOPICS]
    if args.limit:
        cand = cand[:args.limit]
    print(f"건축관련 14주제 시군구 후보 {len(cand)}개 숏리스트 생성 (delay={args.delay}s)", flush=True)

    key = _key()
    client = httpx.Client(timeout=25.0)
    rows = []
    try:
        for i, t in enumerate(cand, 1):
            # 1) 수록기간 (주기·최신연도) — 최신성 필터
            prd = _meta(client, key, t["org_id"], t["tbl_id"], "PRD")
            time.sleep(args.delay)
            prd_se = prd[0].get("PRD_SE") if prd else None
            latest = prd[0].get("END_PRD_DE") if prd else None
            year = _year_of(latest)

            item_count, sample = None, []
            if year >= args.min_year:  # 최신 표만 항목 조회(비용 절약)
                itm = _meta(client, key, t["org_id"], t["tbl_id"], "ITM")
                time.sleep(args.delay)
                item_count = len(itm)
                sample = [r.get("ITM_NM") for r in itm[:6] if r.get("ITM_NM")]

            rows.append({
                "topic": first(t), "org_id": t["org_id"], "tbl_id": t["tbl_id"],
                "tbl_nm": t["tbl_nm"], "prd_se": prd_se, "latest": latest, "year": year,
                "item_count": item_count, "sample_items": sample,
            })
            if i % 25 == 0 or i == len(cand):
                print(f"  {i}/{len(cand)} … (최근 {t['tbl_id']} {prd_se}/{latest})", flush=True)
    finally:
        client.close()

    rows.sort(key=lambda r: (-r["year"], r["topic"]))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "topics": sorted(ARCH_TOPICS),
        "stats": {"total": len(rows),
                  "recent_2018+": sum(1 for r in rows if r["year"] >= 2018),
                  "recent_2023+": sum(1 for r in rows if r["year"] >= 2023)},
        "tables": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n완료 → {args.out}")
    n23 = sum(1 for r in rows if r['year'] >= 2023)
    print(f"  총 {len(rows)}개 · 2023+ 최신 {n23}개")
    print("\n=== 최신 표 상위 15 (연도순) ===")
    for r in rows[:15]:
        print(f"  [{r['topic'][:4]:4}] {r['tbl_id']:14} {r['latest']:>8}  항목{r['item_count']}  {r['tbl_nm'][:38]}")


if __name__ == "__main__":
    main()
