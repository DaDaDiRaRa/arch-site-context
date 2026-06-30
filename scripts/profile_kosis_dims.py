"""① 차원 프로파일링 (obj 구조 발굴법 크랙) — docs/KOSIS_DEPTH_PLAN.md.

KOSIS 다차원 표의 차원 구조를 자동 해부한다. err21(다차원 표 질의 실패)의 근본 해결:
  getMeta type=ITM 응답이 OBJ_NM 으로 **모든 차원(항목·지역·산업·규모…)**과 멤버코드를 담고 있다.
  → 차원별 멤버 + '전체/계' 합계코드 + 지역코드(영등포) 자동 추출 → 표별 차원지도.

이 지도가 있으면 다차원 표도 objL1=지역·objL2=분류전체 식으로 질의 가능 → 편입 토대.
연구·데이터 산출 스크립트(앱 코드 무수정). KOSIS 분당제한 → 슬립.

사용:
    python scripts/profile_kosis_dims.py                    # 내장 고가치 표 셋
    python scripts/profile_kosis_dims.py --tables DT_1BD1035,DT_MLTM_2082
산출(out/kosis_dims.json): 표별 {dimensions[], region_dim, ydp_code, total_codes}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
SHORTLIST = OUT_DIR / "kosis_shortlist.json"
_META = "https://kosis.kr/openapi/statisticsData.do"

# 검증 기준 도시 — 영등포구. 표마다 코드체계가 달라(행안부 11560 / census 11190 …) 이름으로 찾는다.
_TARGET_CITY = "영등포"
# 합계(전체) 멤버로 인정하는 이름·코드.
_TOTAL_NAMES = {"전체", "계", "합계", "총계", "소계", "전산업", "전국"}
_TOTAL_CODES = {"0", "00", "000", "0000"}
# 지역 차원으로 인정하는 OBJ_NM 키워드.
_REGION_HINTS = ("시군구", "행정구역", "시도", "지역", "시·군·구")

# 내장 고가치 표 (Step 1 숏리스트에서 선별). org_id 는 숏리스트에서 보강.
DEFAULT_TABLES = [
    "DT_1BD1035", "DT_1BD1032", "DT_MLTM_2082", "DT_1NW1037",
    "DT_1JU1512", "DT_HIRA4U", "DT_11761_N009", "DT_1LC0001", "DT_408_2006_S0040",
]


def _key() -> str:
    load_dotenv()
    k = os.getenv("KOSIS_KEY")
    if not k:
        sys.exit("KOSIS_KEY 미설정 (.env 확인)")
    return k


def _is_total(itm_id: str | None, itm_nm: str | None) -> bool:
    return (itm_id in _TOTAL_CODES) or bool(itm_nm and itm_nm.strip() in _TOTAL_NAMES)


def profile(client: httpx.Client, key: str, org_id: str, tbl_id: str) -> dict:
    """표 1개 차원 해부. getMeta ITM → OBJ_NM 그룹핑 → 차원지도."""
    r = client.get(_META, params={
        "method": "getMeta", "apiKey": key, "format": "json", "jsonVD": "Y",
        "orgId": org_id, "tblId": tbl_id, "type": "ITM"}, timeout=25.0)
    try:
        rows = json.loads(r.text)
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "ITM 메타 파싱 실패"}
    if not isinstance(rows, list) or not rows:
        return {"ok": False, "reason": "ITM 메타 없음"}

    by_obj: dict = defaultdict(list)
    for x in rows:
        by_obj[(x.get("OBJ_ID"), x.get("OBJ_NM"))].append((x.get("ITM_ID"), x.get("ITM_NM")))

    dims = []
    region_dim = None
    ydp_code = None
    for (oid, onm), members in by_obj.items():
        totals = [mid for mid, mnm in members if _is_total(mid, mnm)]
        is_item = onm == "항목" or oid == "ITEM"
        is_region = any(h in (onm or "") for h in _REGION_HINTS)
        dim = {
            "obj_id": oid, "obj_nm": onm, "is_item": is_item, "is_region": is_region,
            "member_count": len(members),
            "total_codes": totals,  # '전체/계' 코드 — 합계 picking 용
            "sample": [{"id": m, "nm": n} for m, n in members[:6]],
        }
        if is_region:
            region_dim = oid
            hit = [m for m, n in members if _TARGET_CITY in (n or "")]
            ydp_code = hit[0] if hit else None
            dim["target_city"] = {"name": _TARGET_CITY, "code": ydp_code}
        dims.append(dim)

    # 차원 분류 요약
    n_class = sum(1 for d in dims if not d["is_item"] and not d["is_region"])
    return {
        "ok": True,
        "dim_count": len(dims),
        "n_classification": n_class,  # 지역·항목 외 분류차원 수 (objL2,3,… 필요수)
        "region_dim": region_dim,
        "ydp_code": ydp_code,
        "dimensions": dims,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="KOSIS 차원 프로파일러 (① 크랙)")
    ap.add_argument("--tables", default="", help="콤마구분 tbl_id. 비우면 내장 고가치 셋")
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--out", default=str(OUT_DIR / "kosis_dims.json"))
    args = ap.parse_args()

    tbls = [t.strip() for t in args.tables.split(",") if t.strip()] or DEFAULT_TABLES
    # org_id 는 숏리스트에서 보강 (없으면 101 기본)
    org_map = {}
    if SHORTLIST.exists():
        for r in json.loads(SHORTLIST.read_text(encoding="utf-8"))["tables"]:
            org_map[r["tbl_id"]] = r["org_id"]

    key = _key()
    client = httpx.Client(timeout=25.0)
    result = {}
    try:
        for tbl in tbls:
            org = org_map.get(tbl, "101")
            res = profile(client, key, org, tbl)
            time.sleep(args.delay)
            result[tbl] = {"org_id": org, **res}
            if res["ok"]:
                cls = [d["obj_nm"] for d in res["dimensions"] if not d["is_item"] and not d["is_region"]]
                tot = next((d["total_codes"] for d in res["dimensions"] if not d["is_item"] and not d["is_region"]), [])
                print(f"  ✓ {tbl:18} 차원{res['dim_count']} (분류 {res['n_classification']}: {cls}) "
                      f"영등포={res['ydp_code']} 분류전체코드={tot}")
            else:
                print(f"  ✗ {tbl:18} {res['reason']}")
    finally:
        client.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "profiled_at": datetime.now().isoformat(timespec="seconds"),
        "tables": result,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n완료 → {args.out}")


if __name__ == "__main__":
    main()
