# -*- coding: utf-8 -*-
"""VWorld 항공영상(Satellite) 타일 수신 게이트 (P2).

지도 합성 전에 'VWorld 타일이 이 서버에서 실제로 받아지는가'만 확인한다.
성공(jpeg 저장) → VWorld 확정. 401/도메인거부 → 메시지 그대로 보여주고 카카오 스카이뷰 전환 판단.

실행:
  D:\\APPS\\arch-site-context\\.venv\\Scripts\\python.exe scripts\\check_vworld_tile.py
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# 프로젝트 루트(.env, ./out) 기준 잡기
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def deg2tile(lat: float, lon: float, z: int) -> tuple[int, int]:
    """위경도(WGS84) → 슬리피맵 타일 좌표 (x, y). 표준 웹메르카토르 타일링."""
    lat_rad = math.radians(lat)
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def main() -> int:
    key = os.getenv("VWORLD_KEY")
    if not key:
        print("[FAIL] VWORLD_KEY 가 .env 에 없습니다.")
        return 2
    referer = os.getenv("VWORLD_REFERER")  # 도메인 잠금 대응 (선택)

    # 서울시청 부근, z=16
    lat, lon, z = 37.5663, 126.9779, 16
    x, y = deg2tile(lat, lon, z)

    # URL 경로 순서 주의: /{z}/{y}/{x}.jpeg
    url = f"https://api.vworld.kr/req/wmts/1.0.0/{key}/Satellite/{z}/{y}/{x}.jpeg"

    headers = {}
    if referer:
        headers["Referer"] = referer

    masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "(짧음)"
    print(f"VWORLD_KEY  : {masked}")
    print(f"Referer     : {referer or '(없음 — 생략)'}")
    print(f"좌표        : 서울시청 lat={lat}, lon={lon}, z={z}")
    print(f"타일 x,y    : {x}, {y}")
    print(f"요청 URL    : https://api.vworld.kr/req/wmts/1.0.0/****/Satellite/{z}/{y}/{x}.jpeg")
    print("-" * 60)

    try:
        r = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=True)
    except Exception as e:
        print(f"[FAIL] 네트워크 오류: {type(e).__name__}: {e}")
        return 1

    ctype = r.headers.get("content-type", "")
    body = r.content
    is_jpeg = body[:2] == b"\xff\xd8"  # JPEG 매직바이트

    print(f"상태코드    : {r.status_code}")
    print(f"Content-Type: {ctype}")
    print(f"바이트수    : {len(body)}")

    # 200 이라도 본문이 jpeg 아니면 실패로 본다 (VWorld는 200+에러본문 사례 있음)
    if r.status_code == 200 and is_jpeg and len(body) > 100:
        out_dir = ROOT / "out"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"vworld_sat_z{z}_{x}_{y}.jpeg"
        out_path.write_bytes(body)
        print("-" * 60)
        print(f"[OK] VWorld 타일 수신 성공 → 저장: {out_path}")
        print("     => VWorld 확정. P3(지도 합성) 진행 가능.")
        return 0

    # 실패 — 상태코드 + 응답 본문 앞부분 그대로 노출 (401/도메인거부 메시지 판단용)
    print("-" * 60)
    print("[FAIL] jpeg 타일을 받지 못했습니다. 응답 본문 앞부분:")
    preview = body[:600]
    try:
        print(preview.decode("utf-8", errors="replace"))
    except Exception:
        print(repr(preview))
    print("-" * 60)
    print("     => 401/도메인거부 등이면 카카오 스카이뷰 전환 판단 (CLAUDE.md P2 규칙).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
