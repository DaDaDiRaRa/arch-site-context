"""
건물 API 실측 스크립트 v3
==========================
변경점: 실측 전용 키를 우선 사용 (site-context 운영 키와 분리)
  - VWORLD_TEST_KEY 가 있으면 그걸 사용, 없으면 VWORLD_KEY 폴백
  - VWORLD_TEST_DOMAIN 없으면 빈 문자열 (기타키는 도메인 불필요)

.env (site-context 폴더, A안):
    VWORLD_KEY=기존_운영_키
    VWORLD_DOMAIN=기존_도메인
    VWORLD_TEST_KEY=새_기타_개발키        <- 실측은 이걸로
    # VWORLD_TEST_DOMAIN=                 <- 기타키면 비워둬도 됨

실행:
    cd D:\APPS\arch-site-context
    C:\...\python.exe test_building_api_v3.py
"""

import os, sys, json, math, requests
from dotenv import load_dotenv

load_dotenv()
# 실측 전용 키 우선, 없으면 운영 키 폴백
KEY = os.environ.get("VWORLD_TEST_KEY") or os.environ.get("VWORLD_KEY")
DOMAIN = os.environ.get("VWORLD_TEST_DOMAIN", "")
USING = "TEST" if os.environ.get("VWORLD_TEST_KEY") else "운영(폴백)"

ADDRESS = "대전광역시 서구 괴정동 358"
RADIUS_M = 250

GEO_URL  = "https://api.vworld.kr/req/address"
DATA_URL = "https://api.vworld.kr/req/data"

BUILDING_CANDIDATES = ["LT_C_SPBD", "LT_C_BLDINFO", "LT_C_BULD"]
CADASTRAL = "LP_PA_CBND_BUBUN"


def die(msg):
    print(f"\n[중단] {msg}"); sys.exit(1)


def check_setup():
    if not KEY:
        die(".env에 VWORLD_TEST_KEY(또는 VWORLD_KEY) 없음.")
    print(f"[키] {USING} 키 사용 (길이 {len(KEY)}, 앞4 {KEY[:4]}***) / domain='{DOMAIN}'")


def geocode(address):
    print(f"\n[1] 지오코딩: {address}")
    p = {"service":"address","request":"getcoord","version":"2.0",
         "crs":"epsg:4326","address":address,"format":"json",
         "type":"PARCEL","key":KEY,"domain":DOMAIN}
    data = requests.get(GEO_URL, params=p, timeout=15).json()
    if data.get("response",{}).get("status") != "OK":
        die("지오코딩 실패:\n"+json.dumps(data,ensure_ascii=False)[:600])
    pt = data["response"]["result"]["point"]
    lon, lat = float(pt["x"]), float(pt["y"])
    print(f"    좌표 = {lon}, {lat}")
    return lon, lat


def geom_filter_box(lon, lat, radius_m):
    dlat = radius_m / 111320.0
    dlon = radius_m / (111320.0 * math.cos(math.radians(lat)))
    box = f"BOX({lon-dlon},{lat-dlat},{lon+dlon},{lat+dlat})"
    print(f"    geomFilter = {box}")
    return box


def query_data(dataset, box, label):
    print(f"\n[조회] {label}  (data={dataset})")
    p = {"service":"data","request":"GetFeature","data":dataset,
         "key":KEY,"domain":DOMAIN,"format":"json",
         "geomFilter":box,"geometry":"true","size":"5","crs":"EPSG:4326"}
    r = requests.get(DATA_URL, params=p, timeout=30)
    print(f"    HTTP {r.status_code}")
    try:
        data = r.json()
    except Exception:
        print("    JSON 아님:", r.text[:300]); return False
    resp = data.get("response", {})
    status = resp.get("status")
    print(f"    status = {status}")
    if status != "OK":
        print("    ->", json.dumps(resp, ensure_ascii=False)[:300]); return False
    fc = resp.get("result", {}).get("featureCollection", {})
    feats = fc.get("features", [])
    print(f"    피처 개수 = {len(feats)}")
    if not feats:
        print("    -> 이 영역에 데이터 없음"); return True
    props = feats[0].get("properties", {})
    print(f"    ★ 속성 필드 ({len(props)}개):")
    for k, v in props.items():
        print(f"        {k} = {v}")
    floor_keys = [k for k in props if any(t in k.lower() for t in
                  ["floor","층","stor","fl","ground","지상","height","높이","elev","gro","und"])]
    print(f"    ★ 층수/높이 후보: {floor_keys if floor_keys else '없음'}")
    gt = feats[0].get("geometry", {}).get("type")
    print(f"    ★ 도형 타입: {gt}")
    return True


if __name__ == "__main__":
    print("="*56); print(" 건물 API 실측 v3"); print("="*56)
    check_setup()
    lon, lat = geocode(ADDRESS)
    box = geom_filter_box(lon, lat, RADIUS_M)
    print("\n[2] 건물 데이터셋 탐색")
    for cand in BUILDING_CANDIDATES:
        if query_data(cand, box, f"건물 후보 {cand}"):
            break
    print("\n[3] 연속지적도 (footprint/PNU 확인 + domain 검증)")
    query_data(CADASTRAL, box, "연속지적")
    print("\n"+"="*56)
    print(" 끝. 각 조회의 '속성 필드'와 '층수/높이 후보'를 공유해주세요.")
    print("="*56)
