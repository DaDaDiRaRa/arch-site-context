"""국토부 data.go.kr API — 아파트 실거래가 · 표준지 공시지가 · 건축물대장.

DATA_GO_KR_API_KEY 사용. 각 데이터셋별 활용신청 완료 필요.
미등록(code 30) 등 오류는 graceful 반환 (절대 원칙 3 — 추정 금지, 정직 표시).
XML 응답 → ElementTree 파싱.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import date
from typing import List, Optional, Tuple

import httpx

_BASE = "https://apis.data.go.kr"


def _key() -> str:
    k = os.getenv("DATA_GO_KR_API_KEY", "")
    if not k:
        raise ValueError("DATA_GO_KR_API_KEY 미설정")
    return k


def _check_xml_result(root: ET.Element, label: str) -> None:
    """XML resultCode 확인. 정상(00)이 아니면 ValueError."""
    code = root.findtext("header/resultCode") or root.findtext(".//resultCode") or ""
    if code == "00":
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


# ── 아파트 실거래가 ─────────────────────────────────────────────────────────

def fetch_apt_trade(
    sgg_code: str,
    months: int = 3,
    max_items: int = 10,
    client: Optional[httpx.Client] = None,
) -> Tuple[List[dict], List[str]]:
    """아파트 실거래가 최근 N개월 조회.

    Returns:
        ([{apt_name, area_sqm, price_10k, floor, deal_month}], notes)
    """
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
            r = client.get(
                f"{_BASE}/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
                params={
                    "serviceKey": key,
                    "LAWD_CD": sgg_code,
                    "DEAL_YMD": ym,
                    "pageNo": 1,
                    "numOfRows": 20,
                },
                timeout=12.0,
            )
            r.raise_for_status()
            root = ET.fromstring(r.text)
            try:
                _check_xml_result(root, "아파트실거래가")
            except ValueError as e:
                if "NODATA_ERROR" in str(e):
                    continue
                raise
            for item in root.findall(".//item"):
                if len(trades) >= max_items:
                    break
                raw_price = (item.findtext("거래금액") or "").replace(",", "").strip()
                raw_area = (item.findtext("전용면적") or "").strip()
                if not raw_price or not raw_area:
                    continue
                try:
                    price_10k = int(raw_price)
                    area_sqm = round(float(raw_area), 2)
                except (ValueError, TypeError):
                    continue
                trades.append(
                    {
                        "apt_name": (item.findtext("아파트") or "").strip(),
                        "area_sqm": area_sqm,
                        "price_10k": price_10k,
                        "floor": _int_or_none(item.findtext("층")),
                        "deal_month": ym,
                        "dong": (item.findtext("법정동") or "").strip(),
                    }
                )
        if trades:
            notes.append(f"아파트 실거래가: 최근 {months}개월 기준 (국토부 RTMS, 시군구 평균 아님 — 개별 거래).")
        else:
            notes.append(f"아파트 실거래가: 최근 {months}개월 거래 없음 ({sgg_code}).")
        return trades, notes

    except ValueError as e:
        return [], [str(e)]
    except Exception as e:
        return [], [f"아파트 실거래가 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()


# ── 표준지 공시지가 ─────────────────────────────────────────────────────────

def fetch_land_price(
    lon: float,
    lat: float,
    year: Optional[int] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """좌표 기반 표준지 공시지가 조회.

    Returns:
        ({price_per_sqm, year, pnu}, notes)  또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    stdr_year = year or date.today().year
    own = client is None
    client = client or httpx.Client(timeout=15.0)

    try:
        r = client.get(
            f"{_BASE}/1613000/PblntfStdPclPriceService/getPblntfStdPclPriceAtXY",
            params={
                "serviceKey": key,
                "xAddr": lon,
                "yAddr": lat,
                "stdrYear": stdr_year,
                "pageNo": 1,
                "numOfRows": 1,
            },
            timeout=12.0,
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)
        try:
            _check_xml_result(root, "표준지공시지가")
        except ValueError as e:
            if "NODATA_ERROR" in str(e):
                # 전년도로 재시도
                if stdr_year > 2020:
                    r2 = client.get(
                        f"{_BASE}/1613000/PblntfStdPclPriceService/getPblntfStdPclPriceAtXY",
                        params={
                            "serviceKey": key,
                            "xAddr": lon,
                            "yAddr": lat,
                            "stdrYear": stdr_year - 1,
                            "pageNo": 1,
                            "numOfRows": 1,
                        },
                        timeout=12.0,
                    )
                    root = ET.fromstring(r2.text)
                    _check_xml_result(root, "표준지공시지가(전년)")
                    stdr_year -= 1
                else:
                    raise
            else:
                raise

        item = root.find(".//item")
        if item is None:
            return None, ["표준지공시지가: 해당 좌표 데이터 없음."]

        raw_price = (item.findtext("stdPclc") or "").replace(",", "").strip()
        if not raw_price:
            return None, ["표준지공시지가: 가격 필드 없음."]

        price = int(raw_price)
        pnu = (item.findtext("pnu") or "").strip()
        notes.append(f"표준지공시지가: {stdr_year}년 기준 (국토부, 개별 필지 아닐 수 있음 — 참고).")
        return {"price_per_sqm": price, "year": stdr_year, "pnu": pnu}, notes

    except ValueError as e:
        return None, [str(e)]
    except Exception as e:
        return None, [f"표준지공시지가 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()


# ── 건축물대장 ──────────────────────────────────────────────────────────────

def fetch_building(
    sido: str,
    sigungu: str,
    dong: str,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """건축물대장 기본 정보 조회 (시도+시군구+법정동 기준 첫 번째 결과).

    Returns:
        ({purpose, floors_above, floors_below, year_built, total_area_sqm,
          site_area_sqm, bcr, far}, notes)  또는 (None, notes)
    """
    notes: List[str] = []
    try:
        key = _key()
    except ValueError as e:
        return None, [str(e)]

    own = client is None
    client = client or httpx.Client(timeout=15.0)

    try:
        r = client.get(
            f"{_BASE}/1613000/BldRgstService_v2/getBldRgstInfoSearch",
            params={
                "serviceKey": key,
                "siDoNm": sido,
                "siGunGuNm": sigungu,
                "bjdongNm": dong,
                "pageNo": 1,
                "numOfRows": 5,
            },
            timeout=12.0,
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)
        _check_xml_result(root, "건축물대장")

        items = root.findall(".//item")
        if not items:
            return None, [f"건축물대장: {sigungu} {dong} 데이터 없음."]

        item = items[0]  # 첫 번째 (면적 최대 기준 정렬이 아님 — 참고용)

        result = {
            "purpose": (item.findtext("mainPurpsCdNm") or item.findtext("etcPurps") or "").strip() or None,
            "floors_above": _int_or_none(item.findtext("grndFlrCnt")),
            "floors_below": _int_or_none(item.findtext("ugrndFlrCnt")),
            "year_built": _year_from_approval(item.findtext("useAprDay")),
            "total_area_sqm": _float_or_none(item.findtext("totArea")),
            "site_area_sqm": _float_or_none(item.findtext("platArea")),
            "bcr": _float_or_none(item.findtext("bcRat")),
            "far": _float_or_none(item.findtext("vlRat")),
        }
        notes.append(f"건축물대장: {sigungu} {dong} 첫 건물 기준 (국토부, 해당 대지 건물과 다를 수 있음 — 참고).")
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
