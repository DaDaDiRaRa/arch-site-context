# -*- coding: utf-8 -*-
"""공공데이터포털 키 등록 확인 게이트 (DEFERRED.md D1).

전국마을회관및경로당표준데이터 API 가 이 키로 조회되는지만 확인한다.
resultCode 00 + 시설명/위경도 → 등록 완료 (경로당 보강 P1.5b 착수 가능).
code 30 → 아직 미등록/미전파 (data.go.kr 활용신청·1~2h 대기).

실행:
  D:\\APPS\\arch-site-context\\.venv\\Scripts\\python.exe scripts\\check_dataportal.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

_URL = "https://api.data.go.kr/openapi/tn_pubr_public_vill_hall_sen_cent_api"


def main() -> int:
    key = os.getenv("DATA_GO_KR_API_KEY")
    if not key:
        print("[FAIL] DATA_GO_KR_API_KEY 가 .env 에 없습니다.")
        return 2

    params = {"serviceKey": key, "pageNo": 1, "numOfRows": 3, "type": "json"}
    print(f"key prefix: {key[:10]}... (len {len(key)})")
    try:
        r = httpx.get(_URL, params=params, timeout=20.0)
    except Exception as e:
        print(f"[FAIL] 네트워크 오류: {type(e).__name__}: {e}")
        return 1

    try:
        data = r.json()
    except Exception:
        print(f"[FAIL] 비-JSON 응답 (앞부분): {r.text[:300]}")
        return 1

    head = data.get("response", {}).get("header", {})
    code = head.get("resultCode")
    msg = head.get("resultMsg")
    print(f"resultCode: {code} | {msg}")

    if code in ("00", 0):
        body = data.get("response", {}).get("body", {})
        items = body.get("items", [])
        if isinstance(items, dict):
            items = items.get("item", [])
        print(f"[OK] 등록 완료. totalCount={body.get('totalCount')}")
        for it in items[:3]:
            print(f"   - {it.get('FLCT_NM')} | LAT {it.get('LAT')} LOT {it.get('LOT')}"
                  f" | {it.get('LCTN_ROAD_NM_ADDR') or it.get('LCTN_LOTNO_ADDR')}")
        print("   => 경로당 보강(P1.5b) 착수 가능. Claude 에게 알려주세요.")
        return 0

    print("[WAIT] 아직 미등록/미전파입니다 (code 30 등).")
    print("   => data.go.kr 활용신청 확인 + 승인 후 1~2시간 뒤 재시도.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
