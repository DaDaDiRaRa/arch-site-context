"""통계청 SGIS OpenAPI — 좌표+반경 → 집계구 → 집계구별 실인구 합산 (D2).

값은 실제 SGIS에서 호출해 가져온다 (절대 원칙 1). 구 평균을 면적으로 쪼개는 보간은
하지 않는다 — 집계구(약 500명 단위) 실인구를 합산한다 (절대 원칙 1·3).

흐름(검증됨, docs/SGIS + [[sgis-radius-population-api]]):
  1) 좌표 WGS84 → UTM-K(5179)            transformation/transcoord
  2) 반경 bbox → 집계구 폴리곤+중심좌표     boundary/userarea (cd=4)
  3) 반경 원 안 집계구만 필터
  4) 집계구 → 읍면동(앞8자리) 그룹 → 인구   stats/population (low_search=1)
  5) tot_ppltn 합산 + 부양비 역산으로 연령비율

집계구는 직접 인구조회 불가(-100) → 읍면동 low_search=1로 펼쳐 받는다.
키 없음/오류/매칭실패는 graceful — None 또는 부분결과 + 정직한 notes (절대 원칙 3).
"""

from __future__ import annotations

import math
import os
import time
from typing import Dict, List, Optional, Tuple

import httpx

from app.services.cache import Cache, default_cache, make_key
from app.services.http_retry import request_with_retry

_BASE = "https://sgisapi.mods.go.kr/OpenAPI3"
_DEFAULT_YEAR = "2023"  # 총조사 인구 (2015~2024). 검증 연도. 필요시 호출부에서 override.


class SgisError(RuntimeError):
    """SGIS 호출 실패 / 인증 실패."""


def _keys() -> Tuple[str, str]:
    ck = os.getenv("SGIS_KEY", "")
    cs = os.getenv("SGIS_SECRET", "")
    if not ck or not cs:
        raise SgisError("SGIS_KEY / SGIS_SECRET 미설정 (.env 확인).")
    return ck, cs


def _get(client: httpx.Client, path: str, params: dict, *, timeout: float = 20.0) -> dict:
    r = request_with_retry(client, "GET", f"{_BASE}/{path}", params=params, timeout=timeout)
    if r.status_code != 200:
        raise SgisError(f"SGIS HTTP {r.status_code}: {r.text[:150]}")
    try:
        return r.json()
    except Exception:
        raise SgisError(f"SGIS 응답 파싱 실패: {r.text[:150]}")


def get_token(client: httpx.Client, cache: Optional[Cache] = None) -> str:
    """accessToken 발급. accessTimeout(만료 epoch ms)까지 캐시 재사용."""
    cache = cache if cache is not None else default_cache
    ckey = make_key("sgis_token")
    cached = cache.get(ckey)
    if cached and cached.get("token") and cached.get("exp", 0) > time.time() + 60:
        return cached["token"]

    ck, cs = _keys()
    j = _get(client, "auth/authentication.json",
             {"consumer_key": ck, "consumer_secret": cs})
    if j.get("errCd") != 0:
        raise SgisError(f"SGIS 인증 실패 errCd={j.get('errCd')}: {j.get('errMsg')}")
    res = j.get("result") or {}
    token = res.get("accessToken")
    if not token:
        raise SgisError("SGIS accessToken 없음.")
    # accessTimeout = 만료 epoch ms (실측). 초로 환산해 캐시.
    try:
        exp = float(res.get("accessTimeout", 0)) / 1000.0
    except Exception:
        exp = time.time() + 3600
    cache.set(ckey, {"token": token, "exp": exp})
    return token


def to_utmk(lat: float, lon: float, token: str, client: httpx.Client) -> Tuple[float, float]:
    """WGS84(4326) → UTM-K(5179) 미터 좌표."""
    j = _get(client, "transformation/transcoord.json",
             {"accessToken": token, "src": "4326", "dst": "5179", "posX": lon, "posY": lat})
    res = j.get("result") or {}
    return float(res["posX"]), float(res["posY"])


def _tongs_in_radius(
    cx: float, cy: float, radius: int, token: str, client: httpx.Client
) -> List[Tuple[str, int]]:
    """반경 원 안에 중심이 든 집계구 [(집계구코드14, 거리m)]. bbox 조회 후 원 필터."""
    j = _get(client, "boundary/userarea.geojson",
             {"accessToken": token, "cd": "4",
              "minx": cx - radius, "miny": cy - radius,
              "maxx": cx + radius, "maxy": cy + radius})
    out: List[Tuple[str, int]] = []
    for f in j.get("features", []):
        p = f.get("properties", {})
        code = p.get("adm_cd")
        try:
            x, y = float(p["x"]), float(p["y"])
        except (KeyError, TypeError, ValueError):
            continue
        d = math.hypot(x - cx, y - cy)
        if code and d <= radius:
            out.append((code, round(d)))
    return out


def _dong_tong_pop(
    dong8: str, year: str, token: str, client: httpx.Client, cache: Optional[Cache]
) -> Dict[str, dict]:
    """읍면동(8자리) → {집계구코드14: 인구행}. 집계구 직접조회 불가 → low_search=1로 펼침."""
    cache = cache if cache is not None else default_cache
    ckey = make_key("sgis_dongpop", dong8, year)
    cached = cache.get(ckey)
    if cached is not None:
        return cached.get("rows", {})
    j = _get(client, "stats/population.json",
             {"accessToken": token, "year": year, "adm_cd": dong8, "low_search": "1"})
    rows: Dict[str, dict] = {}
    for row in (j.get("result") or []):
        code = row.get("adm_cd")
        if code:
            rows[code] = row
    cache.set(ckey, {"rows": rows})
    return rows


def _f(v) -> Optional[float]:
    """'N/A'·'' → None, 그 외 float."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_radius_population(
    lat: float,
    lon: float,
    radius: int = 1000,
    *,
    year: str = _DEFAULT_YEAR,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Optional[dict]:
    """좌표+반경 → 반경 내 추계인구·연령비율 (집계구 합산). 실패 시 None (graceful).

    연령비율(유소년·고령·생산가능)은 집계구별 tot_ppltn + 부양비(유년·노년)에서 인구수를
    역산해 합산 후 재계산한다 — 표준 0-14/15-64/65+ 정의의 정확한 산술(보간 아님).
    부양비 결측 집계구는 총인구엔 포함하되 연령비율 모수에서 제외(note).

    반환 dict: radius, total_pop, tong_count, tong_matched, tong_unmatched,
      youth_share, aged_share, working_share, avg_age, base_year, source, notes.
    """
    own = client is None
    client = client or httpx.Client(timeout=25.0)
    notes: List[str] = []
    try:
        token = get_token(client, cache)
        cx, cy = to_utmk(lat, lon, token, client)
        tongs = _tongs_in_radius(cx, cy, radius, token, client)
        if not tongs:
            return None
        tong_codes = {c for c, _ in tongs}

        # 집계구 → 읍면동 그룹 → 인구맵 (호출수 최소화: 읍면동당 1콜)
        dongs = sorted({c[:8] for c in tong_codes})
        popmap: Dict[str, dict] = {}
        for d in dongs:
            try:
                popmap.update(_dong_tong_pop(d, year, token, client, cache))
            except SgisError as e:
                notes.append(f"읍면동 {d} 집계구 인구 조회 실패: {e}")

        total_pop = 0
        sum_youth = sum_old = sum_work = 0.0
        age_num = age_den = 0.0  # 평균나이 인구가중
        matched = 0
        unmatched: List[str] = []
        ratio_skipped = 0
        for code in tong_codes:
            row = popmap.get(code)
            tot = _f(row.get("tot_ppltn")) if row else None
            if row is None or tot is None:
                unmatched.append(code)
                continue
            matched += 1
            total_pop += int(tot)
            # 평균나이 인구가중
            avg = _f(row.get("avg_age"))
            if avg is not None and tot > 0:
                age_num += avg * tot
                age_den += tot
            # 연령비율 역산: youth/work = J/100, old/work = O/100
            J = _f(row.get("juv_suprt_per"))
            O = _f(row.get("oldage_suprt_per"))
            if J is None or O is None or tot <= 0:
                ratio_skipped += 1
                continue
            denom = 1.0 + J / 100.0 + O / 100.0
            if denom <= 0:
                ratio_skipped += 1
                continue
            work = tot / denom
            sum_work += work
            sum_youth += work * J / 100.0
            sum_old += work * O / 100.0

        if matched == 0:
            notes.append("반경 내 집계구 인구를 하나도 매칭하지 못함.")
            return None

        ratio_pop = sum_youth + sum_old + sum_work
        youth_share = round(sum_youth / ratio_pop * 100, 1) if ratio_pop > 0 else None
        aged_share = round(sum_old / ratio_pop * 100, 1) if ratio_pop > 0 else None
        working_share = round(sum_work / ratio_pop * 100, 1) if ratio_pop > 0 else None
        avg_age = round(age_num / age_den, 1) if age_den > 0 else None

        if unmatched:
            notes.append(
                f"집계구 {len(unmatched)}개 인구 미매칭(무인구·경계 vintage 차) — 합산 제외."
            )
        if ratio_skipped:
            notes.append(f"집계구 {ratio_skipped}개 부양비 결측 — 연령비율 모수 제외(총인구는 포함).")

        return {
            "radius": radius,
            "total_pop": total_pop,
            "tong_count": len(tong_codes),
            "tong_matched": matched,
            "tong_unmatched": len(unmatched),
            "youth_share": youth_share,
            "aged_share": aged_share,
            "working_share": working_share,
            "avg_age": avg_age,
            "base_year": year,
            "source": "sgis",
            "notes": notes,
        }
    finally:
        if own:
            client.close()
