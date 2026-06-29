"""국토부 data.go.kr API — 실거래가(RTMS) · 건축물대장(건축HUB).

DATA_GO_KR_API_KEY 사용. 각 데이터셋별 활용신청 완료 필요.
미등록(code 30) 등 오류는 graceful 반환 (절대 원칙 3 — 추정 금지, 정직 표시).
XML 응답 → ElementTree 파싱.
※ 공시지가는 data.go.kr 미승인 → VWorld 개별공시지가로 우회 (services/vworld.py).
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import date
from typing import List, Optional, Tuple

import httpx

from app.services.http_retry import request_with_retry

_BASE = "https://apis.data.go.kr"


def _key() -> str:
    k = os.getenv("DATA_GO_KR_API_KEY", "")
    if not k:
        raise ValueError("DATA_GO_KR_API_KEY 미설정")
    return k


def _check_xml_result(root: ET.Element, label: str) -> None:
    """XML resultCode 확인. 정상(00)이 아니면 ValueError."""
    code = root.findtext("header/resultCode") or root.findtext(".//resultCode") or ""
    if code in ("00", "000"):  # 서비스에 따라 00(공통) / 000(RTMS)
        return
    msg = root.findtext("header/resultMsg") or root.findtext(".//resultMsg") or ""
    if code == "03":
        raise ValueError(f"{label}: 데이터 없음 (NODATA_ERROR).")
    if code == "30":
        raise ValueError(f"{label}: API 키 미등록(code 30) — data.go.kr 활용신청 필요.")
    raise ValueError(f"{label}: API 오류 {code}: {msg}")


def _deal_months(months: int = 3) -> List[str]:
    """최근 N개월의 YYYYMM 문자열 리스트 (최신순)."""
    today = date.today()
    result = []
    y, m = today.year, today.month
    for _ in range(months):
        result.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return result


# ── 실거래가 (RTMS) — 종류별 레지스트리 ───────────────────────────────────────
# 모두 data.go.kr 1613000/RTMS*, LAWD_CD(시군구5자리)+DEAL_YMD(YYYYMM) 파라미터 공통.
# field 맵: name(단지/지목)·area·price(매매금액 또는 보증금)·monthly(월세, 없으면 None)·extra(부가).
# 검증: scripts/probe — 전부 resultCode=000 작동 확인 (docs/API_VERIFICATION).
_RTMS = {
    "토지매매": {
        "path": "RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade",
        "rent": False, "name": "jimok", "area": "dealArea",
        "price": "dealAmount", "extra": "landUse",  # 지목 / 용도지역
    },
    "아파트매매": {
        "path": "RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
        "rent": False, "name": "aptNm", "area": "excluUseAr",
        "price": "dealAmount", "extra": None,
    },
    "연립다세대매매": {
        "path": "RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade",
        "rent": False, "name": "mhouseNm", "area": "excluUseAr",
        "price": "dealAmount", "extra": "houseType",
    },
    "아파트전월세": {
        "path": "RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
        "rent": True, "name": "aptNm", "area": "excluUseAr",
        "price": "deposit", "monthly": "monthlyRent", "extra": None,
    },
    "오피스텔전월세": {
        "path": "RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
        "rent": True, "name": "offiNm", "area": "excluUseAr",
        "price": "deposit", "monthly": "monthlyRent", "extra": None,
    },
}

# /site 기본 조회 종류 (대지분석 관련도 순 — 토지매매 우선)
DEFAULT_TRADE_KINDS = ["토지매매", "아파트매매", "연립다세대매매", "아파트전월세"]


def _money_10k(v: Optional[str]) -> Optional[int]:
    """'3,900' → 3900 (만원)."""
    if not v:
        return None
    try:
        return int(v.replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def fetch_trades(
    category: str,
    sgg_code: str,
    months: int = 3,
    max_items: int = 5,
    client: Optional[httpx.Client] = None,
) -> Tuple[List[dict], List[str]]:
    """RTMS 실거래가 1종을 최근 N개월 조회 (category = _RTMS 키).

    Returns:
        ([{category, deal_type, name, area_sqm, price_10k, monthly_10k,
           floor, deal_ym, dong, note}], notes)
    """
    spec = _RTMS.get(category)
    if spec is None:
        return [], [f"실거래가: 미지원 종류 '{category}'."]

    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return [], [str(e)]

    own = client is None
    client = client or httpx.Client(timeout=15.0)
    trades: List[dict] = []

    try:
        for ym in _deal_months(months):
            if len(trades) >= max_items:
                break
            r = request_with_retry(
                client,
                "GET",
                f"{_BASE}/1613000/{spec['path']}",
                params={"serviceKey": key, "LAWD_CD": sgg_code, "DEAL_YMD": ym,
                        "pageNo": 1, "numOfRows": 20},
                timeout=12.0,
            )
            r.raise_for_status()
            root = ET.fromstring(r.text)
            try:
                _check_xml_result(root, f"실거래가({category})")
            except ValueError as e:
                if "NODATA_ERROR" in str(e):
                    continue
                raise
            for item in root.findall(".//item"):
                if len(trades) >= max_items:
                    break
                price_10k = _money_10k(item.findtext(spec["price"]))
                if price_10k is None:
                    continue
                monthly_10k = None
                deal_type = "매매"
                if spec["rent"]:
                    monthly_10k = _money_10k(item.findtext(spec.get("monthly", ""))) or 0
                    deal_type = "월세" if monthly_10k > 0 else "전세"
                note = ""
                if spec.get("extra"):
                    note = (item.findtext(spec["extra"]) or "").strip()
                trades.append({
                    "category": category,
                    "deal_type": deal_type,
                    "name": (item.findtext(spec["name"]) or "").strip(),
                    "area_sqm": _float_or_none(item.findtext(spec["area"])),
                    "price_10k": price_10k,
                    "monthly_10k": monthly_10k,
                    "floor": _int_or_none(item.findtext("floor")),
                    "deal_ym": ym,
                    "dong": (item.findtext("umdNm") or "").strip(),
                    "note": note,
                })
        if not trades:
            notes.append(f"{category}: 최근 {months}개월 거래 없음 ({sgg_code}).")
        return trades, notes

    except ValueError as e:
        return [], [str(e)]
    except Exception as e:
        return [], [f"{category} 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()


# ── 건축물대장 (건축HUB, PNU 기준) ──────────────────────────────────────────
# (표준지공시지가는 data.go.kr 미승인 → VWorld 개별공시지가로 우회: services/vworld.py)
_HUB = "https://apis.data.go.kr/1613000/BldRgstHubService"


def _parse_pnu(pnu: str) -> Optional[Tuple[str, str, str, str, str]]:
    """PNU 19자리 → (sigunguCd5, bjdongCd5, platGbCd, bun4, ji4) 또는 None.

    PNU = 법정동코드(10) + 필지구분(1) + 본번(4) + 부번(4).
    대장 platGbCd: 0=대지, 1=산 (PNU 필지구분 1=일반→0, 2=산→1).
    """
    if not pnu or len(pnu) != 19 or not pnu.isdigit():
        return None
    plat_gb = "0" if pnu[10] == "1" else "1"
    return pnu[0:5], pnu[5:10], plat_gb, pnu[11:15], pnu[15:19]


def _hub_items(
    client: httpx.Client, key: str, op: str, params: dict
) -> List[ET.Element]:
    """건축HUB 한 오퍼레이션 호출 → item 리스트 (실패·무데이터는 빈 리스트)."""
    r = request_with_retry(
        client,
        "GET",
        f"{_HUB}/{op}",
        params={**params, "serviceKey": key, "_type": "xml", "numOfRows": 10, "pageNo": 1},
        timeout=12.0,
    )
    r.raise_for_status()
    root = ET.fromstring(r.text)
    _check_xml_result(root, f"건축물대장({op})")
    return root.findall(".//item")


def fetch_building(
    pnu: str,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """건축HUB 건축물대장 — VWorld pnu(필지) 기준 조회.

    표제부(getBrTitleInfo)에서 대표건물(연면적 최대)을 뽑고,
    총괄표제부(getBrRecapTitleInfo)가 있으면 단지 전체 건폐율·용적률·연면적으로 보정.

    Returns:
        ({name, purpose, floors_above, floors_below, year_built, total_area_sqm,
          site_area_sqm, bcr, far}, notes)  또는 (None, notes)
    """
    notes: List[str] = []
    parsed = _parse_pnu(pnu)
    if parsed is None:
        return None, ["건축물대장: 필지번호(PNU) 없음 — 공시지가 조회 실패 시 건너뜀."]
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    sigungu, bjdong, plat_gb, bun, ji = parsed
    parcel_params = {"sigunguCd": sigungu, "bjdongCd": bjdong,
                     "platGbCd": plat_gb, "bun": bun, "ji": ji}
    own = client is None
    client = client or httpx.Client(timeout=15.0)

    try:
        items = _hub_items(client, key, "getBrTitleInfo", parcel_params)
        if not items:
            return None, [f"건축물대장: 해당 필지({pnu}) 표제부 없음 (미등재 대지일 수 있음)."]

        # 대표건물 = 연면적 최대
        main = max(items, key=lambda it: _float_or_none(it.findtext("totArea")) or 0.0)
        result = {
            "name": (main.findtext("bldNm") or "").strip() or None,
            "purpose": (main.findtext("mainPurpsCdNm") or main.findtext("etcPurps") or "").strip() or None,
            "floors_above": _int_or_none(main.findtext("grndFlrCnt")),
            "floors_below": _int_or_none(main.findtext("ugrndFlrCnt")),
            "year_built": _year_from_approval(main.findtext("useAprDay")),
            "total_area_sqm": _float_or_none(main.findtext("totArea")),
            "site_area_sqm": _float_or_none(main.findtext("platArea")),
            "bcr": _float_or_none(main.findtext("bcRat")),
            "far": _float_or_none(main.findtext("vlRat")),
        }

        # 총괄표제부(단지 전체)가 있으면 대지 기준 건폐율·용적률·연면적으로 보정
        scope = "대표건물"
        try:
            recaps = _hub_items(client, key, "getBrRecapTitleInfo", parcel_params)
        except Exception:
            recaps = []
        if recaps:
            rc = recaps[0]
            for fld, key_name in (("totArea", "total_area_sqm"), ("platArea", "site_area_sqm"),
                                  ("bcRat", "bcr"), ("vlRat", "far")):
                v = _float_or_none(rc.findtext(fld))
                if v is not None:
                    result[key_name] = v
            scope = "단지 전체"

        addr = (main.findtext("newPlatPlc") or "").strip()
        building_cnt = len(items)
        multi = f" (필지 내 {building_cnt}개 동, {scope} 기준)" if building_cnt > 1 else ""
        notes.append(f"건축물대장: {addr or pnu}{multi} (건축HUB — 참고).")
        return result, notes

    except ValueError as e:
        return None, [str(e)]
    except Exception as e:
        return None, [f"건축물대장 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()


# ── 공통 유틸 ───────────────────────────────────────────────────────────────

def _int_or_none(v: Optional[str]) -> Optional[int]:
    if not v:
        return None
    try:
        return int(v.strip())
    except (ValueError, TypeError):
        return None


def _float_or_none(v: Optional[str]) -> Optional[float]:
    if not v:
        return None
    try:
        return round(float(v.strip()), 2)
    except (ValueError, TypeError):
        return None


def _year_from_approval(v: Optional[str]) -> Optional[int]:
    """사용승인일 'YYYYMMDD' → 년도 int."""
    if not v or len(v) < 4:
        return None
    try:
        return int(v[:4])
    except (ValueError, TypeError):
        return None
