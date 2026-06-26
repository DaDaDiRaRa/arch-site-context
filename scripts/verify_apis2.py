# -*- coding: utf-8 -*-
"""터읽기 — 2차 정밀 검증 (verify_apis2.py).

1차(verify_apis.py)에서 403/500/401 난 항목들의 원인 분리:
 - data.go.kr 부동산: '승인된' 엔드포인트 vs '미승인(아파트매매)' 대조
 - TMAP: appKey 헤더방식 / 대체 엔드포인트
 - 문화기반시설: data.go.kr(B553457) vs kcisa(CULTURE_KEY) 어느 쪽 키인지
 - 에어코리아: B552584 승인여부 재확인
"""
from __future__ import annotations
import os, sys, json, xml.etree.ElementTree as ET
from pathlib import Path
import httpx
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DGK = os.getenv("DATA_GO_KR_API_KEY", "")
SGG = "11560"        # 영등포구
YM = "202604"        # 데이터 확실한 과거월


def line(name, verdict, http, extra=""):
    print(f"  [{verdict:16s}] {name:<34s} http={http}  {extra}")


def datago_xml(name, path, params):
    p = dict(params); p["serviceKey"] = DGK
    try:
        r = httpx.get("https://apis.data.go.kr" + path, params=p, timeout=20)
        t = r.text.lstrip()
        if r.status_code == 403 or "Forbidden" in t[:40]:
            return line(name, "NOT_APPROVED", r.status_code, "403 Forbidden(미승인/미구독)")
        if r.status_code == 500 or "Unexpected" in t[:40]:
            return line(name, "NOT_APPROVED", r.status_code, "500 Unexpected(미승인 추정)")
        try:
            root = ET.fromstring(t)
        except Exception:
            return line(name, "?", r.status_code, t[:80])
        code = root.findtext(".//resultCode") or "?"
        msg = root.findtext(".//resultMsg") or ""
        cnt = len(root.findall(".//item"))
        if code == "00":
            return line(name, "WORKS", r.status_code, f"items={cnt}")
        if code == "03":
            return line(name, "NO_DATA(키OK)", r.status_code, "code03 해당월 거래없음")
        if code in ("30", "31"):
            return line(name, "KEY_NOT_APPROVED", r.status_code, f"code{code}")
        return line(name, "ERR", r.status_code, f"code{code} {msg}")
    except Exception as e:
        return line(name, "NETWORK_ERR", "-", f"{type(e).__name__}: {e}")


print("\n== data.go.kr 부동산 실거래가 (승인목록 대조) ==")
# 미승인 추정 (1차 403): 아파트 매매
datago_xml("아파트매매(#33,Dev)", "/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
           {"LAWD_CD": SGG, "DEAL_YMD": YM, "numOfRows": 3})
# 승인목록(섹션0): 토지매매 / 연립다세대매매 / 공장창고매매 / 아파트전월세 / 오피스텔전월세
datago_xml("토지매매[승인]", "/1613000/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade",
           {"LAWD_CD": SGG, "DEAL_YMD": YM, "numOfRows": 3})
datago_xml("연립다세대매매[승인]", "/1613000/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade",
           {"LAWD_CD": SGG, "DEAL_YMD": YM, "numOfRows": 3})
datago_xml("공장창고등매매[승인]", "/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade",
           {"LAWD_CD": SGG, "DEAL_YMD": YM, "numOfRows": 3})
datago_xml("아파트전월세[승인]", "/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
           {"LAWD_CD": SGG, "DEAL_YMD": YM, "numOfRows": 3})
datago_xml("오피스텔전월세[승인]", "/1613000/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
           {"LAWD_CD": SGG, "DEAL_YMD": YM, "numOfRows": 3})

print("\n== data.go.kr 기타 (1차 미승인/오류 재확인) ==")
datago_xml("표준지공시지가(#35)", "/1613000/PblntfStdPclPriceService/getPblntfStdPclPriceAtXY",
           {"xAddr": 126.978, "yAddr": 37.566, "stdrYear": 2025, "numOfRows": 1})
datago_xml("건축물대장(#48)", "/1613000/BldRgstService_v2/getBldRgstInfoSearch",
           {"siDoNm": "서울특별시", "siGunGuNm": "영등포구", "bjdongNm": "여의도동", "numOfRows": 3})
datago_xml("에어코리아 측정값(#86)", "/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty",
           {"sidoName": "서울", "returnType": "xml", "numOfRows": 3, "ver": "1.0"})

print("\n== 문화기반시설(#134) — 두 경로 ==")
# (a) data.go.kr B553457 (DATA_GO_KR_API_KEY)
datago_xml("문화기반시설총람[data.go.kr]", "/B553457/rgnCltrFcltExmn/getRgnCltrFcltExmn",
           {"numOfRows": 3, "pageNo": 1, "type": "xml"})
# (b) kcisa (CULTURE_KEY) — 공연정보(API_CCA_148) 로 키 인증여부만 확인
ck = os.getenv("CULTURE_KEY", "")
for num in ("API_CCA_145", "API_CCA_148", "API_CCA_149"):
    try:
        r = httpx.get(f"https://api.kcisa.kr/openapi/{num}/request",
                      params={"serviceKey": ck, "numOfRows": 3, "pageNo": 1}, timeout=15)
        t = r.text.lstrip()
        if r.status_code == 200 and ("<item>" in t or "NORMAL" in t or '"resultCode":"00"' in t):
            line(f"kcisa {num}[CULTURE_KEY]", "WORKS", 200, t[:60])
        elif r.status_code == 401 or "Unauthorized" in t:
            line(f"kcisa {num}[CULTURE_KEY]", "AUTH_FAIL", r.status_code, "Unauthorized")
        else:
            line(f"kcisa {num}[CULTURE_KEY]", "?", r.status_code, t[:80])
    except Exception as e:
        line(f"kcisa {num}[CULTURE_KEY]", "NETWORK_ERR", "-", str(e)[:60])

print("\n== TMAP(#103) — 전달방식/엔드포인트 분리 ==")
tk = os.getenv("TMAP_KEY", "")
# (a) appKey 헤더 + POI
try:
    r = httpx.get("https://apis.openapi.sk.com/tmap/pois",
                  params={"version": 1, "searchKeyword": "서울역", "count": 3},
                  headers={"appKey": tk}, timeout=15)
    line("TMAP POI(헤더appKey)", "WORKS" if r.status_code == 200 else "AUTH_FAIL",
         r.status_code, r.text[:70])
except Exception as e:
    line("TMAP POI(헤더appKey)", "NETWORK_ERR", "-", str(e)[:60])
# (b) 보행자 경로 POST (대중교통/길찾기 product 확인)
try:
    r = httpx.get("https://apis.openapi.sk.com/tmap/geo/reversegeocoding",
                  params={"version": 1, "lat": 37.566, "lon": 126.978, "appKey": tk}, timeout=15)
    line("TMAP reversegeo(쿼리)", "WORKS" if r.status_code == 200 else "AUTH_FAIL",
         r.status_code, r.text[:70])
except Exception as e:
    line("TMAP reversegeo(쿼리)", "NETWORK_ERR", "-", str(e)[:60])
