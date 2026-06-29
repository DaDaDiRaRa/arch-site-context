# -*- coding: utf-8 -*-
"""터읽기 — 전체 API 연결 검증 하니스 (verify_apis.py).

.env 의 모든 키를 실제 엔드포인트로 호출해 연결 상태를 분류한다.
키 값은 절대 출력하지 않는다. 결과는 표 + JSON(scratchpad) 으로 남긴다.

실행:
  .venv\\Scripts\\python.exe scripts\\verify_apis.py

판정(verdict):
  WORKS            정상 응답 + 데이터 (또는 정상 NO_DATA)
  NO_DATA          키는 유효하나 해당 조건 데이터 없음 (정상 신호)
  KEY_NOT_APPROVED data.go.kr 활용신청 미승인/미전파 (code 30/31)
  AUTH_FAIL        키 자체가 무효/오류 (401 / 인증키 오류)
  WRONG_ENDPOINT   404/경로 또는 파라미터 문제
  NO_API           공개 REST API 자체가 없음 (파일/대시보드만)
  NETWORK_ERR      네트워크/타임아웃/파싱 오류
  SKIP             검증 범위 밖 (사유 표기)
"""
from __future__ import annotations

import json
import os
import sys
import math
import traceback
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv

try:  # Windows 콘솔 cp949 → UTF-8 강제 (한글/em-dash 출력)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

SCRATCH = Path(os.getenv("VERIFY_OUT", str(ROOT / "out")))
SCRATCH.mkdir(parents=True, exist_ok=True)

RESULTS: list[dict] = []

# 서울시청 부근 좌표 — 공통 테스트 지점
LON, LAT = 126.9779, 37.5663
SGG_CODE = "11560"  # 영등포구 (행안부 LAWD_CD 앞5자리)


def rec(group, name, env, verdict, http=None, signal="", sample="", note=""):
    RESULTS.append({
        "group": group, "name": name, "env": env, "verdict": verdict,
        "http": http, "signal": signal, "sample": sample[:160], "note": note[:200],
    })


def has(env_name) -> bool:
    return bool(os.getenv(env_name))


def _trunc(o, n=140):
    s = json.dumps(o, ensure_ascii=False) if not isinstance(o, str) else o
    return s[:n]


# ─────────────────────────────────────────────────────────────────────────────
# 기존 핵심 키
# ─────────────────────────────────────────────────────────────────────────────

def probe_kakao():
    env = "KAKAO_KEY"
    if not has(env):
        return rec("기존핵심", "카카오 로컬(주소→좌표)", env, "SKIP", note="키 없음")
    try:
        r = httpx.get(
            "https://dapi.kakao.com/v2/local/search/address.json",
            params={"query": "서울특별시 영등포구 국회대로 608", "size": 1},
            headers={"Authorization": f"KakaoAK {os.getenv(env)}"}, timeout=10,
        )
        if r.status_code == 401:
            return rec("기존핵심", "카카오 로컬(주소→좌표)", env, "AUTH_FAIL", r.status_code, "401")
        docs = r.json().get("documents", [])
        if docs:
            d = docs[0]
            return rec("기존핵심", "카카오 로컬(주소→좌표)", env, "WORKS", r.status_code,
                       "documents>0", f"{d.get('address_name')} ({d.get('x')},{d.get('y')})")
        return rec("기존핵심", "카카오 로컬(주소→좌표)", env, "NO_DATA", r.status_code, "documents=0")
    except Exception as e:
        return rec("기존핵심", "카카오 로컬(주소→좌표)", env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def _deg2tile(lat, lon, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def probe_vworld():
    env = "VWORLD_KEY"
    if not has(env):
        return rec("기존핵심", "VWorld 위성타일(WMTS)", env, "SKIP", note="키 없음")
    z = 15
    x, y = _deg2tile(LAT, LON, z)
    url = f"https://api.vworld.kr/req/wmts/1.0.0/{os.getenv(env)}/Satellite/{z}/{y}/{x}.jpeg"
    try:
        r = httpx.get(url, timeout=15)
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and ctype.startswith("image"):
            return rec("기존핵심", "VWorld 위성타일(WMTS)", env, "WORKS", 200,
                       ctype, f"{len(r.content)} bytes jpeg, z{z}")
        return rec("기존핵심", "VWorld 위성타일(WMTS)", env, "AUTH_FAIL", r.status_code,
                   ctype, _trunc(r.text))
    except Exception as e:
        return rec("기존핵심", "VWorld 위성타일(WMTS)", env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def probe_vworld_data():
    """VWorld 데이터(2D) API — 개별공시지가(LP_PA_CBND_BUBUN). data.go.kr 공시지가 우회 핵심.

    ★domain 파라미터가 등록 서비스URL과 일치해야 함(불일치 시 INCORRECT_KEY).
    """
    env = "VWORLD_KEY"
    if not has(env):
        return rec("기존핵심", "VWorld 데이터(개별공시지가)", env, "SKIP", note="키 없음")
    domain = os.getenv("VWORLD_DOMAIN") or "arch-site-context-30350777436.asia-northeast3.run.app"
    try:
        r = httpx.get("https://api.vworld.kr/req/data", params={
            "service": "data", "version": "2.0", "request": "GetFeature", "format": "json",
            "size": 1, "page": 1, "data": "LP_PA_CBND_BUBUN",
            "geomFilter": f"POINT({LON} {LAT})", "key": os.getenv(env), "domain": domain,
        }, timeout=15)
        body = r.json().get("response", {})
        status = body.get("status")
        if status == "OK":
            feats = (body.get("result", {}) or {}).get("featureCollection", {}).get("features", [])
            jiga = feats[0].get("properties", {}).get("jiga") if feats else None
            return rec("기존핵심", "VWorld 데이터(개별공시지가)", env, "WORKS", 200,
                       "status=OK", f"jiga={jiga}")
        err = body.get("error", {}) or {}
        v = "AUTH_FAIL" if err.get("code") == "INCORRECT_KEY" else "WRONG_ENDPOINT"
        return rec("기존핵심", "VWorld 데이터(개별공시지가)", env, v, r.status_code,
                   err.get("code", status), note=f"domain={domain}")
    except Exception as e:
        return rec("기존핵심", "VWorld 데이터(개별공시지가)", env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def probe_kosis():
    env = "KOSIS_KEY"
    if not has(env):
        return rec("기존핵심", "KOSIS 통계(모드 A)", env, "SKIP", note="키 없음")
    try:
        from app.services.kosis import fetch_table
        res = fetch_table("101", "DT_1B04005N", SGG_CODE, year=None, obj_l2="ALL")
        rows = res.get("rows", []) if isinstance(res, dict) else []
        if rows:
            return rec("기존핵심", "KOSIS 통계(모드 A)", env, "WORKS", 200,
                       f"rows={len(rows)}, year={res.get('year')}", _trunc(rows[0]))
        return rec("기존핵심", "KOSIS 통계(모드 A)", env, "NO_DATA", 200, "rows=0")
    except Exception as e:
        msg = str(e)
        v = "AUTH_FAIL" if ("인증" in msg or "key" in msg.lower()) else "NETWORK_ERR"
        return rec("기존핵심", "KOSIS 통계(모드 A)", env, v, note=f"{type(e).__name__}: {msg}")


def probe_juso():
    env = "JUSO_API_KEY"
    if not has(env):
        return rec("기존핵심", "JUSO 도로명주소(폴백)", env, "SKIP", note="키 없음")
    try:
        r = httpx.get(
            "https://business.juso.go.kr/addrlink/addrLinkApi.do",
            params={"confmKey": os.getenv(env), "currentPage": 1, "countPerPage": 1,
                    "keyword": "국회대로 608", "resultType": "json"}, timeout=10,
        )
        body = r.json()
        common = body.get("results", {}).get("common", {})
        code = common.get("errorCode")
        if code == "0":
            juso = body.get("results", {}).get("juso") or []
            return rec("기존핵심", "JUSO 도로명주소(폴백)", env, "WORKS" if juso else "NO_DATA",
                       r.status_code, f"errorCode=0", _trunc(juso[0]) if juso else "")
        return rec("기존핵심", "JUSO 도로명주소(폴백)", env, "AUTH_FAIL", r.status_code,
                   f"errorCode={code}", common.get("errorMessage", ""))
    except Exception as e:
        return rec("기존핵심", "JUSO 도로명주소(폴백)", env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def probe_anthropic():
    env = "ANTHROPIC_API_KEY"
    if not has(env):
        return rec("기존핵심", "Claude API(서술/물어보기)", env, "SKIP", note="키 없음")
    try:
        import anthropic
        client = anthropic.Anthropic()
        try:
            ct = client.messages.count_tokens(
                model="claude-opus-4-8",
                messages=[{"role": "user", "content": "안녕"}],
            )
            return rec("기존핵심", "Claude API(서술/물어보기)", env, "WORKS", 200,
                       "count_tokens", f"input_tokens={getattr(ct,'input_tokens','?')}, model=claude-opus-4-8")
        except Exception:
            resp = client.messages.create(
                model="claude-opus-4-8", max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return rec("기존핵심", "Claude API(서술/물어보기)", env, "WORKS", 200,
                       "messages.create", f"stop={resp.stop_reason}")
    except Exception as e:
        msg = str(e)
        v = "AUTH_FAIL" if ("401" in msg or "authentication" in msg.lower()) else "NETWORK_ERR"
        return rec("기존핵심", "Claude API(서술/물어보기)", env, v, note=f"{type(e).__name__}: {msg[:160]}")


# ─────────────────────────────────────────────────────────────────────────────
# data.go.kr (단일 키, 데이터셋별 활용신청)
# ─────────────────────────────────────────────────────────────────────────────

def _datago_result_code(text):
    """data.go.kr 표준 응답 → (resultCode, msg). JSON/XML/SOAP fault 모두 처리."""
    t = text.lstrip()
    # SOAP fault (키 미등록 시 자주)
    if "SERVICE_KEY_IS_NOT_REGISTERED" in t or "SERVICE KEY IS NOT REGISTERED" in t:
        return "30", "SERVICE_KEY_IS_NOT_REGISTERED"
    if "LIMITED_NUMBER" in t:
        return "22", "QUOTA_EXCEEDED"
    try:
        if t.startswith("{") or t.startswith("["):
            j = json.loads(t)
            hdr = (j.get("response", {}) or {}).get("header", {}) or {}
            if hdr:
                return str(hdr.get("resultCode")), hdr.get("resultMsg", "")
            # tn_pubr 류는 response.header 동일구조
            return None, None
        root = ET.fromstring(t)
        code = root.findtext(".//resultCode") or root.findtext(".//returnReasonCode")
        msg = root.findtext(".//resultMsg") or root.findtext(".//errMsg") or root.findtext(".//returnAuthMsg")
        return code, msg
    except Exception:
        return None, None


def _classify_datago(text):
    code, msg = _datago_result_code(text)
    if code in ("00", "0", "000"):  # 000 = RTMS 실거래 계열 정상코드
        return "WORKS", code, msg
    if code in ("30", "31"):
        return "KEY_NOT_APPROVED", code, msg
    if code in ("03",):
        return "NO_DATA", code, msg
    if code in ("22",):
        return "NO_DATA", code, "QUOTA(키유효)"
    if code is None:
        return None, None, None
    return "WRONG_ENDPOINT", code, msg


def _datago_probe(name, url, params, http_scheme_note=""):
    env = "DATA_GO_KR_API_KEY"
    if not has(env):
        return rec("data.go.kr", name, env, "SKIP", note="키 없음")
    p = dict(params)
    p["serviceKey"] = os.getenv(env)
    try:
        r = httpx.get(url, params=p, timeout=20)
        verdict, code, msg = _classify_datago(r.text)
        if verdict is None:
            # 헤더 없이 바로 데이터가 온 경우 → 성공 추정
            sample = _trunc(r.text)
            ok = ("items" in r.text or "item" in r.text or '"body"' in r.text)
            return rec("data.go.kr", name, env, "WORKS" if ok else "WRONG_ENDPOINT",
                       r.status_code, "no-header", sample)
        return rec("data.go.kr", name, env, verdict, r.status_code,
                   f"resultCode={code}", _trunc(r.text), note=(msg or "") + http_scheme_note)
    except Exception as e:
        return rec("data.go.kr", name, env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def probe_datago_all():
    # 1) 마을회관/경로당 표준데이터 (DEFERRED D1)
    _datago_probe("경로당·마을회관 표준데이터",
                  "https://api.data.go.kr/openapi/tn_pubr_public_vill_hall_sen_cent_api",
                  {"pageNo": 1, "numOfRows": 3, "type": "json"})
    # 2) 에어코리아 측정소 목록
    _datago_probe("에어코리아 측정소목록(#86)",
                  "https://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getMsrstnList",
                  {"addr": "서울", "pageNo": 1, "numOfRows": 3, "returnType": "json"})
    # 3) 아파트 실거래가
    ym = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y%m")
    _datago_probe("아파트 실거래가(#33)",
                  "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
                  {"LAWD_CD": SGG_CODE, "DEAL_YMD": ym, "pageNo": 1, "numOfRows": 3})
    # 4) 표준지 공시지가 (좌표) — ※ 미승인이어도 무방: 운영은 VWorld 개별공시지가로 우회(probe_vworld_data)
    _datago_probe("표준지 공시지가(#35·VWorld로 우회)",
                  "https://apis.data.go.kr/1613000/PblntfStdPclPriceService/getPblntfStdPclPriceAtXY",
                  {"xAddr": LON, "yAddr": LAT, "stdrYear": date.today().year - 1,
                   "pageNo": 1, "numOfRows": 1})
    # 5) 건축물대장 — 건축HUB 표제부 (구버전 BldRgstService_v2 는 500, 건축HUB 로 전환됨)
    #    PNU 1156011000100280001(여의대로24) → sigunguCd11560 bjdongCd11000 platGb0 bun0028 ji0001
    _datago_probe("건축물대장 표제부(#48 건축HUB)",
                  "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo",
                  {"sigunguCd": "11560", "bjdongCd": "11000", "platGbCd": "0",
                   "bun": "0028", "ji": "0001", "pageNo": 1, "numOfRows": 3, "_type": "xml"})
    # 6) 상가(상권)정보 반경검색 (sangwon demo)
    _datago_probe("상가(상권)정보 반경(#29실API)",
                  "http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius",
                  {"radius": 500, "cx": LON, "cy": LAT, "type": "json",
                   "pageNo": 1, "numOfRows": 5})
    # 7) 응급의료기관 (국립중앙의료원 E-GEN)
    _datago_probe("응급의료기관 목록(#125)",
                  "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire",
                  {"Q0": "서울특별시", "Q1": "영등포구", "pageNo": 1, "numOfRows": 3, "_type": "json"})
    # 8) HIRA 병원정보 (심평원)
    _datago_probe("HIRA 병원정보(#123)",
                  "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList",
                  {"sidoCd": "110000", "sgguCd": "110019", "pageNo": 1, "numOfRows": 3, "_type": "json"})
    # 9) 전국 어린이집 표준데이터 (보건복지부)
    _datago_probe("어린이집 표준데이터(#126)",
                  "https://api.data.go.kr/openapi/tn_pubr_public_child_house_api",
                  {"pageNo": 1, "numOfRows": 3, "type": "json"})
    # 10) 학원·교습소 (행안부 표준)
    _datago_probe("학원·교습소 현황(#118)",
                  "https://api.data.go.kr/openapi/tn_pubr_public_aca_insti_api",
                  {"pageNo": 1, "numOfRows": 3, "type": "json"})


# ─────────────────────────────────────────────────────────────────────────────
# 신규 키 (별도 포털)
# ─────────────────────────────────────────────────────────────────────────────

def probe_kma():
    env = "KMA_KEY"
    if not has(env):
        return rec("신규포털", "기상청 단기예보(#97)", env, "SKIP", note="키 없음")
    # 가장 가까운 발표시각 선택 (간단히 어제 2300)
    bd = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    try:
        r = httpx.get(
            "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst",
            params={"pageNo": 1, "numOfRows": 10, "dataType": "JSON",
                    "base_date": bd, "base_time": "2300", "nx": 60, "ny": 127,
                    "authKey": os.getenv(env)}, timeout=15,
        )
        if r.status_code == 401:
            return rec("신규포털", "기상청 단기예보(#97)", env, "AUTH_FAIL", 401, "HTTP 401",
                       note="authKey 무효 또는 계정 휴대폰 미등록")
        try:
            j = r.json()
            code = j.get("response", {}).get("header", {}).get("resultCode")
            items = j.get("response", {}).get("body", {}).get("items", {})
            if code == "00":
                return rec("신규포털", "기상청 단기예보(#97)", env, "WORKS", 200,
                           "resultCode=00", _trunc(items))
            return rec("신규포털", "기상청 단기예보(#97)", env, "NO_DATA", 200, f"resultCode={code}")
        except Exception:
            return rec("신규포털", "기상청 단기예보(#97)", env, "WRONG_ENDPOINT", r.status_code,
                       "non-JSON", _trunc(r.text))
    except Exception as e:
        return rec("신규포털", "기상청 단기예보(#97)", env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def probe_rone():
    env = "RONE_KEY"
    if not has(env):
        return rec("신규포털", "부동산원 R-ONE(#39~41)", env, "SKIP", note="키 없음")
    try:
        r = httpx.get(
            "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do",
            params={"KEY": os.getenv(env), "STATBL_ID": "A_2024_00045",
                    "DTACYCLE_CD": "MM", "Type": "json", "pIndex": 1, "pSize": 5}, timeout=20,
        )
        t = r.text
        if "ERROR-290" in t or "인증키가 유효하지 않" in t:
            return rec("신규포털", "부동산원 R-ONE(#39~41)", env, "AUTH_FAIL", r.status_code, "ERROR-290")
        try:
            j = r.json()
        except Exception:
            return rec("신규포털", "부동산원 R-ONE(#39~41)", env, "WRONG_ENDPOINT", r.status_code,
                       "non-JSON", _trunc(t))
        res = j.get("RESULT", {})
        if isinstance(res, dict) and str(res.get("CODE", "")).startswith("ERROR"):
            return rec("신규포털", "부동산원 R-ONE(#39~41)", env, "AUTH_FAIL", r.status_code,
                       res.get("CODE"), res.get("MESSAGE", ""))
        # 성공: SttsApiTblData 키 아래 list/head
        keys = [k for k in j.keys() if k != "RESULT"]
        return rec("신규포털", "부동산원 R-ONE(#39~41)", env, "WORKS", r.status_code,
                   "data rows", _trunc({k: "…" for k in keys}))
    except Exception as e:
        return rec("신규포털", "부동산원 R-ONE(#39~41)", env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def probe_seoul():
    env = "SEOUL_API_KEY"
    if not has(env):
        return rec("신규포털", "서울 열린데이터(#22소음/생활인구)", env, "SKIP", note="키 없음")
    key = os.getenv(env)
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/SearchParkInfoService/1/5/"
    try:
        r = httpx.get(url, timeout=15)
        j = r.json()
        # 두 형태: {SERVICE:{RESULT:{CODE}}} 또는 {RESULT:{CODE}}
        result = None
        if "RESULT" in j:
            result = j["RESULT"]
        else:
            for v in j.values():
                if isinstance(v, dict) and "RESULT" in v:
                    result = v["RESULT"]; break
        code = (result or {}).get("CODE", "")
        if code == "INFO-000":
            return rec("신규포털", "서울 열린데이터(#22소음/생활인구)", env, "WORKS", r.status_code,
                       "INFO-000", "SearchParkInfoService rows")
        if code in ("INFO-100", "INFO-300"):
            return rec("신규포털", "서울 열린데이터(#22소음/생활인구)", env, "AUTH_FAIL", r.status_code,
                       code, (result or {}).get("MESSAGE", ""))
        if code in ("INFO-200",):
            return rec("신규포털", "서울 열린데이터(#22소음/생활인구)", env, "NO_DATA", r.status_code, code)
        return rec("신규포털", "서울 열린데이터(#22소음/생활인구)", env, "WORKS" if not code else "WRONG_ENDPOINT",
                   r.status_code, code or "no-RESULT", _trunc(j))
    except Exception as e:
        return rec("신규포털", "서울 열린데이터(#22소음/생활인구)", env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def probe_tmap():
    env = "TMAP_KEY"
    if not has(env):
        return rec("신규포털", "TMAP 대중교통/POI(#103)", env, "SKIP", note="키 없음")
    try:
        r = httpx.get(
            "https://apis.openapi.sk.com/tmap/pois",
            params={"version": 1, "searchKeyword": "서울역", "count": 3,
                    "appKey": os.getenv(env)}, timeout=15,
        )
        if r.status_code in (401, 403):
            return rec("신규포털", "TMAP 대중교통/POI(#103)", env, "AUTH_FAIL", r.status_code,
                       _trunc(r.text))
        j = r.json()
        pois = j.get("searchPoiInfo", {}).get("pois", {}).get("poi", [])
        if pois:
            return rec("신규포털", "TMAP 대중교통/POI(#103)", env, "WORKS", r.status_code,
                       f"pois={len(pois)}", pois[0].get("name", ""))
        return rec("신규포털", "TMAP 대중교통/POI(#103)", env, "NO_DATA", r.status_code, _trunc(j))
    except Exception as e:
        return rec("신규포털", "TMAP 대중교통/POI(#103)", env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def probe_neis():
    env = "NEIS_KEY"
    if not has(env):
        return rec("신규포털", "NEIS 학교현황(#117)", env, "SKIP", note="키 없음")
    try:
        r = httpx.get(
            "https://open.neis.go.kr/hub/schoolInfo",
            params={"KEY": os.getenv(env), "Type": "json", "pIndex": 1, "pSize": 5,
                    "SCHUL_NM": "여의도고등학교"}, timeout=15,
        )
        j = r.json()
        if "schoolInfo" in j:
            head = j["schoolInfo"][0]["head"]
            code = head[1]["RESULT"]["CODE"]
            rows = j["schoolInfo"][1].get("row", [])
            return rec("신규포털", "NEIS 학교현황(#117)", env, "WORKS", r.status_code,
                       code, rows[0].get("SCHUL_NM", "") if rows else "")
        # 오류는 {"RESULT":{"CODE":...}}
        code = j.get("RESULT", {}).get("CODE", "")
        if code in ("INFO-300", "ERROR-300", "INFO-100"):
            return rec("신규포털", "NEIS 학교현황(#117)", env, "AUTH_FAIL", r.status_code,
                       code, j.get("RESULT", {}).get("MESSAGE", ""))
        if code == "INFO-200":
            return rec("신규포털", "NEIS 학교현황(#117)", env, "NO_DATA", r.status_code, code)
        return rec("신규포털", "NEIS 학교현황(#117)", env, "WRONG_ENDPOINT", r.status_code,
                   code or "?", _trunc(j))
    except Exception as e:
        return rec("신규포털", "NEIS 학교현황(#117)", env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def probe_kopis():
    env = "KOPIS_KEY"
    if not has(env):
        return rec("신규포털", "KOPIS 공연시설(#134b)", env, "SKIP", note="키 없음")
    try:
        r = httpx.get(
            "http://www.kopis.or.kr/openApi/restful/prfplc",
            params={"service": os.getenv(env), "cpage": 1, "rows": 5}, timeout=15,
        )
        t = r.text
        try:
            root = ET.fromstring(t)
        except Exception:
            return rec("신규포털", "KOPIS 공연시설(#134b)", env, "WRONG_ENDPOINT", r.status_code,
                       "non-XML", _trunc(t))
        # 오류: <returncode>02</returncode>(키 미등록) / <returnReasonCode> / 서비스키 문구
        rc = root.findtext(".//returncode")
        if rc and rc != "00":
            errmsg = root.findtext(".//errmsg") or ""
            return rec("신규포털", "KOPIS 공연시설(#134b)", env, "KEY_NOT_APPROVED", r.status_code,
                       f"returncode={rc}", errmsg or "키 미등록/재등록 필요")
        if "서비스키" in t or "errMsg" in t or root.findtext(".//returnReasonCode"):
            return rec("신규포털", "KOPIS 공연시설(#134b)", env, "AUTH_FAIL", r.status_code,
                       "service key err", _trunc(t))
        places = root.findall(".//db")
        if places:
            return rec("신규포털", "KOPIS 공연시설(#134b)", env, "WORKS", r.status_code,
                       f"db={len(places)}", places[0].findtext("fcltynm") or "")
        return rec("신규포털", "KOPIS 공연시설(#134b)", env, "NO_DATA", r.status_code, _trunc(t))
    except Exception as e:
        return rec("신규포털", "KOPIS 공연시설(#134b)", env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def probe_library():
    env = "LIBRARY_KEY"
    if not has(env):
        return rec("신규포털", "도서관정보나루(#122)", env, "SKIP", note="키 없음")
    try:
        r = httpx.get(
            "https://data4library.kr/api/libSrch",
            params={"authKey": os.getenv(env), "format": "json", "pageNo": 1,
                    "pageSize": 5, "region": 11}, timeout=15,
        )
        try:
            j = r.json()
        except Exception:
            t = r.text
            if "인증키" in t or "error" in t.lower():
                return rec("신규포털", "도서관정보나루(#122)", env, "AUTH_FAIL", r.status_code, _trunc(t))
            return rec("신규포털", "도서관정보나루(#122)", env, "WRONG_ENDPOINT", r.status_code, _trunc(t))
        resp = j.get("response", {})
        if "error" in resp:
            return rec("신규포털", "도서관정보나루(#122)", env, "AUTH_FAIL", r.status_code,
                       _trunc(resp.get("error")))
        libs = resp.get("libs", [])
        if libs:
            return rec("신규포털", "도서관정보나루(#122)", env, "WORKS", r.status_code,
                       f"libs={len(libs)}", _trunc(libs[0].get("lib", {}).get("libName", "")))
        return rec("신규포털", "도서관정보나루(#122)", env, "NO_DATA", r.status_code, _trunc(j))
    except Exception as e:
        return rec("신규포털", "도서관정보나루(#122)", env, "NETWORK_ERR", note=f"{type(e).__name__}: {e}")


def probe_culture():
    """CULTURE_KEY: kcisa(api.kcisa.kr) 또는 data.go.kr(B553457) 둘 중 하나.
    둘 다 시도해 어느 쪽 키인지 판별."""
    env = "CULTURE_KEY"
    if not has(env):
        return rec("신규포털", "문화기반시설(#134)", env, "SKIP", note="키 없음")
    key = os.getenv(env)
    # 시도 A: data.go.kr B553457 전국문화기반시설총람
    try:
        r = httpx.get(
            "http://apis.data.go.kr/B553457/rgnCltrFcltExmnv1/clifLtrm1",
            params={"serviceKey": key, "pageNo": 1, "numOfRows": 3, "resultType": "json"}, timeout=15,
        )
        v, code, msg = _classify_datago(r.text)
        if v == "WORKS":
            return rec("신규포털", "문화기반시설(#134)", env, "WORKS", r.status_code,
                       f"data.go.kr resultCode={code}", _trunc(r.text))
        a_note = f"data.go.kr→{v}({code})"
    except Exception as e:
        a_note = f"data.go.kr→ERR({type(e).__name__})"
    # 시도 B: kcisa 공통 엔드포인트 인증 확인 (API_CCA_145 = 공연전시; 인증여부만 판별)
    try:
        r2 = httpx.get(
            "https://api.kcisa.kr/openapi/API_CCA_145/request",
            params={"serviceKey": key, "numOfRows": 3, "pageNo": 1}, timeout=15,
        )
        t2 = r2.text
        if "NORMAL" in t2 or "<item>" in t2 or '"resultCode":"00"' in t2 or "00" == (_datago_result_code(t2)[0] or ""):
            return rec("신규포털", "문화기반시설(#134)", env, "WORKS", r2.status_code,
                       "kcisa API_CCA_145 인증OK", note=a_note + " | kcisa키로 추정")
        if "SERVICE_KEY" in t2 or "등록되지" in t2 or "30" == (_datago_result_code(t2)[0] or ""):
            return rec("신규포털", "문화기반시설(#134)", env, "KEY_NOT_APPROVED", r2.status_code,
                       "kcisa 키 미인증", _trunc(t2), note=a_note)
        return rec("신규포털", "문화기반시설(#134)", env, "WRONG_ENDPOINT", r2.status_code,
                   "정확한 API_CCA 번호 필요", _trunc(t2),
                   note=a_note + " | kcisa 데이터셋 번호 확인 필요")
    except Exception as e:
        return rec("신규포털", "문화기반시설(#134)", env, "NETWORK_ERR",
                   note=a_note + f" | kcisa ERR {type(e).__name__}: {e}")


def probe_sbiz365():
    env = "SBIZ365_KEY"
    if not has(env):
        return rec("신규포털", "소상공인365 상권분석(#29·30)", env, "SKIP", note="키 없음")
    # 조사결과: sbiz365.or.kr 은 대시보드/파일다운로드만 — REST OpenAPI 없음.
    return rec("신규포털", "소상공인365 상권분석(#29·30)", env, "NO_API", note=(
        "sbiz365 는 대시보드·파일(CSV/PDF)만. 실거래 매출/폐업/창업·빈상가 REST API 없음. "
        "키는 포털/iframe용. 실 API 는 data.go.kr B553077 storeListInRadius(상가정보) 뿐."))


def probe_eum():
    env = "EUM_KEY"
    if not has(env):
        return rec("범위밖", "토지이음 EUM(규제)", env, "SKIP", note="키 없음")
    # INTEGRATION.md/DEFERRED D6: 규제정보는 arch-law-diagnose 영역. 터읽기 범위 밖.
    return rec("범위밖", "토지이음 EUM(규제)", env, "SKIP", note=(
        "규제정보=arch-law-diagnose 담당(INTEGRATION.md). 터읽기 범위 밖 — 미검증 보류(DEFERRED D6)."))


# ─────────────────────────────────────────────────────────────────────────────

PROBES = [
    probe_kakao, probe_vworld, probe_vworld_data, probe_kosis, probe_juso, probe_anthropic,
    probe_datago_all,
    probe_kma, probe_rone, probe_seoul, probe_tmap, probe_neis,
    probe_kopis, probe_library, probe_culture, probe_sbiz365, probe_eum,
]


def main():
    print("터읽기 API 연결 검증 시작…\n")
    for fn in PROBES:
        try:
            fn()
        except Exception as e:
            rec("?", fn.__name__, "?", "NETWORK_ERR", note=f"probe crash: {e}\n{traceback.format_exc()[:200]}")

    # 결과 먼저 저장 (출력 중 오류 나도 보존)
    out = SCRATCH / "verify_apis_result.json"
    out.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")

    # 출력
    order = {"WORKS": 0, "NO_DATA": 1, "KEY_NOT_APPROVED": 2, "WRONG_ENDPOINT": 3,
             "AUTH_FAIL": 4, "NO_API": 5, "NETWORK_ERR": 6, "SKIP": 7}
    width = max(len(r["name"]) for r in RESULTS) + 1
    cur = None
    for r in sorted(RESULTS, key=lambda x: (x["group"], order.get(x["verdict"], 9))):
        if r["group"] != cur:
            cur = r["group"]
            print(f"\n── {cur} " + "─" * 40)
        line = f"  [{r['verdict']:16s}] {r['name']:<{width}} {r['signal']}"
        print(line)
        if r["note"]:
            print(f"       └ {r['note']}")

    # 요약
    from collections import Counter
    c = Counter(r["verdict"] for r in RESULTS)
    print("\n" + "=" * 56)
    print("요약: " + "  ".join(f"{k}={v}" for k, v in sorted(c.items(), key=lambda x: order.get(x[0], 9))))
    print(f"\n상세 JSON: {out}")


if __name__ == "__main__":
    main()
