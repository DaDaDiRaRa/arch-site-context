"""Phase 2 — KOSIS 항목코드 자동 해석 (docs/KOSIS_DEPTH_PLAN.md).

Phase 1 카탈로그(out/kosis_catalog.json)의 시군구 후보 표를 실제 itmId=ALL 질의로
introspect 해서 옥석을 가린다 — 이름에 '행정구역'이 있어도 시도전용(§8.6 함정)이면 제외.

각 표를 영등포(11560)로 질의 → 응답 분석:
  · 시군구 행(C1=11560 등 5자리)이 나오면 → 진짜 시군구 해석 가능
  · 항목코드(ITM_ID/ITM_NM)·분류(C2)·단위·최신연도 자동 추출
  · 데이터 없으면 정직하게 '미해석'으로 기록 (추정 안 함, 절대 원칙 3)

읽기 전용. KOSIS 분당 제한 → 호출 사이 슬립. 캐시(out/kosis_cache) 재사용.

사용:
    python scripts/resolve_kosis_items.py --topic 주거 --org 101 --limit 15
    python scripts/resolve_kosis_items.py --topic 인구 --org 101 --limit 30 --delay 0.4
산출(out/kosis_resolved.json): 표별 {sigungu_ok, items[], region_level, year, sample_regions}
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
# 데이터 질의(검증용)와 메타 질의(구조 역추출)
_DATA = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
_META = "https://kosis.kr/openapi/statisticsData.do"

# 검증 기준 지역 — 영등포구(행안부 11560). 시군구 해석되면 응답 C1 에 이 코드가 떠야 함.
_TEST_SGG = "11560"


def _key() -> str:
    load_dotenv()
    k = os.getenv("KOSIS_KEY")
    if not k:
        sys.exit("KOSIS_KEY 미설정 (.env 확인)")
    return k


def _meta(client: httpx.Client, key: str, org_id: str, tbl_id: str, type_: str) -> list:
    """getMeta(type=ITM|PRD) — 표 구조 역추출. 에러/실패는 빈 리스트."""
    p = {"method": "getMeta", "apiKey": key, "format": "json", "jsonVD": "Y",
         "orgId": org_id, "tblId": tbl_id, "type": type_}
    try:
        r = client.get(_META, params=p, timeout=25.0)
        d = json.loads(r.text)
        return d if isinstance(d, list) else []
    except Exception:  # noqa: BLE001
        return []


def _introspect(client: httpx.Client, key: str, org_id: str, tbl_id: str, delay: float) -> dict:
    """표 메타(ITM·PRD)로 항목·주기·최신연도 역추출 + 영등포 데이터로 시군구 해석 검증.

    데이터 직접질의는 표마다 주기(연/5년)·차원이 달라 불안정 → 메타 우선(§8.6 교훈).
    """
    # 1) 항목 메타 (항목코드·이름·단위)
    itm_rows = _meta(client, key, org_id, tbl_id, "ITM")
    time.sleep(delay)
    if not itm_rows:
        return {"sigungu_ok": False, "reason": "항목메타 없음(접근불가)"}
    items = [{"itm_id": r.get("ITM_ID"), "itm_nm": r.get("ITM_NM"), "unit": r.get("UNIT_NM")}
             for r in itm_rows]

    # 2) 수록기간 메타 (주기·최신연도) — 구버전(오래된) 표 거르기용
    prd_rows = _meta(client, key, org_id, tbl_id, "PRD")
    time.sleep(delay)
    prd_se = prd_rows[0].get("PRD_SE") if prd_rows else None
    latest = prd_rows[0].get("END_PRD_DE") if prd_rows else None

    # 3) 시군구 해석 검증 — 올바른 주기로 영등포(11560) 질의
    prd_se_param = {"5년": "F", "3년": "F", "1년": "Y", "년": "Y", "분기": "Q", "월": "M"}.get(prd_se, "Y")
    sigungu_ok = False
    region_note = ""
    try:
        dp = {"method": "getList", "apiKey": key, "format": "json", "jsonVD": "Y",
              "orgId": org_id, "tblId": tbl_id, "itmId": "ALL", "objL1": _TEST_SGG,
              "prdSe": prd_se_param, "newEstPrdCnt": "1"}
        r = client.get(_DATA, params=dp, timeout=25.0)
        d = json.loads(r.text)
        time.sleep(delay)
        if isinstance(d, list) and d:
            sigungu_ok = True  # 영등포(행안부코드)로 실데이터 → 시군구·reg 코드 확정
            region_note = "reg(행안부) 단순질의로 해석"
        elif isinstance(d, dict):
            # err20/21 = 다차원 표라 objL2/L3 필수(범용질의 한계). census/시도전용과 구분 불가
            # → 'objL 튜닝 필요'로 정직하게 표기 (false negative 방지, 절대 원칙 3). Phase 3 대상.
            region_note = f"objL 튜닝 필요(err{d.get('err')}) — 다차원/census, Phase3 수동확정"
        else:
            region_note = "영등포 0건 — 시도전용/census 의심"
    except Exception as e:  # noqa: BLE001
        region_note = f"검증질의 실패:{type(e).__name__}"

    return {
        "sigungu_ok": sigungu_ok,
        "items": items,
        "item_count": len(items),
        "prd_se": prd_se,
        "latest": latest,
        "region_note": region_note,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="KOSIS 항목코드 자동 해석 (Phase 2)")
    ap.add_argument("--topic", default="", help="최상위 주제 필터 (예: 주거·인구). 비우면 전체")
    ap.add_argument("--org", default="", help="제공기관 org_id 필터 (예: 101)")
    ap.add_argument("--limit", type=int, default=15, help="introspect 할 표 개수 상한")
    ap.add_argument("--delay", type=float, default=0.4, help="호출 간 슬립(초)")
    ap.add_argument("--out", default=str(OUT_DIR / "kosis_resolved.json"))
    args = ap.parse_args()

    if not CATALOG.exists():
        sys.exit(f"{CATALOG} 없음 — 먼저 mine_kosis_catalog.py 실행")
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    sig = cat["sigungu"]

    def first(t: dict) -> str:
        return t["topic_path"].split(" > ")[0] if t["topic_path"] else ""

    cand = [t for t in sig
            if (not args.topic or first(t) == args.topic)
            and (not args.org or t["org_id"] == args.org)]
    cand = cand[:args.limit]
    print(f"대상 {len(cand)}개 introspect (topic={args.topic or 'ALL'}, org={args.org or 'ALL'})")

    key = _key()
    client = httpx.Client(timeout=25.0)
    resolved = []
    ok = 0
    try:
        for i, t in enumerate(cand, 1):
            res = _introspect(client, key, t["org_id"], t["tbl_id"], args.delay)
            entry = {**{k: t[k] for k in ("org_id", "tbl_id", "tbl_nm")}, **res}
            resolved.append(entry)
            if res.get("sigungu_ok"):
                ok += 1
                items_preview = ", ".join(it["itm_nm"] or "?" for it in res["items"][:4])
                print(f"  [{i}/{len(cand)}] ✓ {t['tbl_id']:14} 항목{res['item_count']:>3} {res['prd_se']}/{res['latest']}  · {items_preview}")
            else:
                rn = res.get("region_note") or res.get("reason", "")
                print(f"  [{i}/{len(cand)}] ✗ {t['tbl_id']:14} 항목{res.get('item_count','?')} {res.get('prd_se','')}/{res.get('latest','')}  {rn}")
    finally:
        client.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "resolved_at": datetime.now().isoformat(timespec="seconds"),
        "filter": {"topic": args.topic or "ALL", "org": args.org or "ALL", "limit": args.limit},
        "stats": {"total": len(cand), "sigungu_ok": ok},
        "tables": resolved,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n완료 → {args.out}  (시군구 해석 {ok}/{len(cand)})")


if __name__ == "__main__":
    main()
