"""행안부 주민등록 인구통계 (rdoa.jumin.go.kr) — 행정동별 인구+세대.

KOSIS OpenAPI 는 읍면동 단위 **세대수**가 없다 (인구는 DT_1B04005N 읍면동, 세대는
시군구 DT_1B040B3 까지). 행안부 주민등록 데이터개방(rdoa) 포털이 행정동별 인구+세대를
**무키·전국·월별**로 제공 → 이걸 호출한다. 값은 실제로 가져온다 (절대 원칙 1).

⚠ REST API 아님 — 폼 POST 후 **결과표 HTML 파싱**(스크래핑). 관건은 hidden `paramUrl`
필드와 세션(JSESSIONID), 그리고 시군구당 ~10행 **페이지네이션**. 서버 구조가 바뀌면
파서 갱신 필요 (§2 bus-factor). 월별 데이터라 (시군구,년월) 캐시로 호출 최소화.
실패/구조변경/빈결과는 graceful — None + 정직한 notes (절대 원칙 3).
엔드포인트·파라미터 상세는 메모리 [[jumin-rdoa-population-household-api]].
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

import httpx

from app.services.cache import Cache, default_cache, make_key
from app.services.http_retry import request_with_retry

try:  # lxml 은 배포/개발에 설치(requirements). 없으면 graceful 비활성.
    from lxml import html as _LH
except ImportError:  # pragma: no cover
    _LH = None

_URL = "https://rdoa.jumin.go.kr/openStats/selectConAdmmPpltnHh"
_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": _URL}
_MAX_PAGES = 20  # 시군구 행정동 수 여유 (페이지당 ~10)


def _int(s: str) -> Optional[int]:
    try:
        return int((s or "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _float(s: str) -> Optional[float]:
    try:
        return float((s or "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _shift_ym(ym: str, months: int = -1) -> str:
    """YYYYMM 을 months 만큼 이동."""
    y, m = int(ym[:4]), int(ym[4:])
    idx = (y * 12 + (m - 1)) + months
    return f"{idx // 12}{idx % 12 + 1:02d}"


def _default_ym() -> str:
    """최신 가용 후보 = 지난달 (당월 통계는 아직 미공개일 수 있음)."""
    t = date.today()
    return _shift_ym(f"{t.year}{t.month:02d}", -1)


def _col_idx(heads: list, *labels: str) -> Optional[int]:
    """헤더 목록에서 label 포함 컬럼의 인덱스 (첫 매치). 없으면 None."""
    for i, h in enumerate(heads):
        if any(lab in h for lab in labels):
            return i
    return None


def _parse_table(html_text: str) -> Dict[str, dict]:
    """결과표 HTML → {행정기관코드(H10): {name, population, households, per_household}}.

    ⚠ rdoa 는 REST 아닌 HTML 스크래핑 → 컬럼 순서가 바뀌면 오파싱 위험(§2 bus-factor).
    고정 인덱스 대신 **헤더 라벨에서 컬럼 인덱스를 유도**(재배치에 자동 대응),
    헤더 유도 실패 시에만 기존 고정 위치(7/8)로 폴백한다.
    """
    doc = _LH.fromstring(html_text)
    out: Dict[str, dict] = {}
    for tbl in doc.xpath("//table"):
        heads = [(x.text_content() or "").strip() for x in tbl.xpath(".//th")]
        if not any("세대수" in h for h in heads):
            continue
        # 헤더에서 컬럼 위치 유도 (통계년월·행정기관코드·시도·시군구·행정동·통·반·총인구수·세대수·…)
        i_code = _col_idx(heads, "행정기관코드", "기관코드")
        i_name = _col_idx(heads, "행정동", "읍면동", "동명")
        i_pop = _col_idx(heads, "총인구", "인구수")
        i_hh = _col_idx(heads, "세대수")
        header_ok = None not in (i_code, i_pop, i_hh)
        for tr in tbl.xpath(".//tr"):
            c = [(x.text_content() or "").strip() for x in tr.xpath("./td")]
            if header_ok and max(i_code, i_pop, i_hh) < len(c):
                code = c[i_code]
                if code.isdigit() and len(code) == 10:
                    out[code] = {
                        "name": c[i_name] if (i_name is not None and i_name < len(c)) else "",
                        "population": _int(c[i_pop]),
                        "households": _int(c[i_hh]),
                        "per_household": None,
                    }
            elif len(c) >= 9 and c[1].isdigit() and len(c[1]) == 10:
                # 헤더 유도 실패 → 고정 위치 폴백 (검증된 현행 구조)
                out[c[1]] = {
                    "name": c[4],
                    "population": _int(c[7]),
                    "households": _int(c[8]),
                    "per_household": _float(c[9]) if len(c) > 9 else None,
                }
        break
    return out


def _fetch_pages(client: httpx.Client, sgg10: str, ctpv10: str, ym: str) -> Dict[str, dict]:
    """세션 확보 후 전 페이지 순회 → {H코드: 통계}. 실패 시 빈 dict."""
    try:
        request_with_retry(client, "GET", _URL, timeout=15.0)  # JSESSIONID 확보
    except Exception:
        return {}
    param_url = f"admmCd={sgg10}&lv=3&regSeCd=1&srchFrYm={ym}&srchToYm={ym}"
    dongs: Dict[str, dict] = {}
    for page in range(1, _MAX_PAGES + 1):
        form = {
            "lv": "3", "ctpvCd": ctpv10, "sggCd": sgg10, "dongCd": "", "regSeCd": "1",
            "srchFrYear": ym[:4], "srchFrMon": ym[4:], "srchToYear": ym[:4], "srchToMon": ym[4:],
            "curPage": str(page), "paramUrl": param_url,
        }
        try:
            r = request_with_retry(client, "POST", _URL, data=form, timeout=30.0)
        except Exception:
            break
        if r.status_code != 200:
            break
        rows = _parse_table(r.content.decode("utf-8", "ignore"))
        fresh = {k: v for k, v in rows.items() if k not in dongs}
        if not fresh:  # 더 이상 새 행정동 없음 → 끝
            break
        dongs.update(fresh)
    return dongs


def fetch_dong_stats(
    sgg_code: str,
    ym: Optional[str] = None,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[Optional[dict], List[str]]:
    """시군구의 **행정동별 주민등록 인구+세대** (행안부 rdoa).

    Args:
        sgg_code: 행안부 시군구코드 5자리 (동작구 11590).
        ym: 조회 년월 YYYYMM. None 이면 지난달부터 최대 3개월 역순 탐색.
    Returns:
        ({"ym","scope","dongs":{H코드:{name,population,households,per_household}}}, notes)
        또는 (None, notes). H코드 = 카카오 coord_to_hdong 의 10자리와 동일 → 매칭 가능.
    """
    notes: List[str] = []
    if _LH is None:
        return None, ["행안부 인구·세대: lxml 미설치 (requirements 확인)."]
    sgg = (sgg_code or "").strip()
    if len(sgg) != 5 or not sgg.isdigit():
        return None, [f"행안부 인구·세대: 시군구코드 형식 오류 ('{sgg_code}')."]

    cache = cache if cache is not None else default_cache
    sgg10 = sgg + "00000"
    ctpv10 = sgg[:2] + "00000000"

    candidates = [ym] if ym else [_default_ym(), _shift_ym(_default_ym(), -1), _shift_ym(_default_ym(), -2)]

    own = client is None
    client = client or httpx.Client(timeout=30.0, headers=_HEADERS, follow_redirects=True)
    try:
        for target in candidates:
            ckey = make_key("jumin", sgg10, target)
            cached = cache.get(ckey)
            if cached is not None:
                return cached.get("data"), cached.get("notes", [])
            dongs = _fetch_pages(client, sgg10, ctpv10, target)
            if dongs:
                data = {"ym": target, "scope": sgg, "dongs": dongs}
                note = (f"행안부 인구·세대: {sgg} {len(dongs)}개 행정동 "
                        f"({target[:4]}.{target[4:]} 주민등록, 행안부 rdoa).")
                cache.set(ckey, {"data": data, "notes": [note]})
                return data, [note]
        return None, [f"행안부 인구·세대: {sgg} 데이터 없음 (조회 {candidates})."]
    except Exception as e:  # noqa: BLE001 — 스크래핑 견고화, 어떤 예외도 graceful
        return None, [f"행안부 인구·세대(rdoa) 오류: {type(e).__name__}: {str(e)[:120]}"]
    finally:
        if own:
            client.close()
