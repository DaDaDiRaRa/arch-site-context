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
    except (ValueError, TypeError):
        exp = 0.0
    if exp <= time.time():
        # 파싱실패·과거·결측 → 1h 추정 대신 보수적 단기 TTL(10분).
        # (실토큰이 더 일찍 죽으면 죽은 토큰을 1시간 재사용해 '데이터 공백'으로 오인하는 것 방지)
        exp = time.time() + 600
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


# ─────────────────────────────────────────────────────────────────────────────
# 대지 재해위험 (홍수·산사태 위험지도 영향범위 포함 여부) — SGIS ndsm
# 위험 영향범위에 '대지가 속한 읍면동'이 포함되는지 = 위험 사실(Y/N). 판단은 사람 (절대 원칙 5).
# ─────────────────────────────────────────────────────────────────────────────

_HAZARDS = {
    # key: (영향범위 읍면동목록, 영향범위 통계보드, 표시명)
    "flood": ("floodRiskAdmCdList.json", "floodRiskDataBoard.json", "홍수위험지도"),
    "landslide": ("lndsldWarnAdmCdList.json", "lndsldWarnDataBoard.json", "산사태위험지도"),
}


# DataBoard 에서 뽑을 영향지표 (총합행 기준). iem_nm 그대로.
# 노후건물·지하건물은 홍수 침수 위험과 직결 (지하 침수·노후 취약). 응답에 없으면 자동 생략.
_BOARD_IEMS = ("인구", "가구", "주택", "사업체", "노후건물", "지하건물")


def _board_exposures(rows: list) -> List[dict]:
    """DataBoard rows → [{metric, affected, total, unit}] (핵심 iem 총합행)."""
    out: List[dict] = []
    if not isinstance(rows, list):
        return out
    by_iem = {it.get("iem_nm"): it for it in rows}
    for iem in _BOARD_IEMS:
        item = by_iem.get(iem)
        if not item:
            continue
        tot = next((d for d in item.get("data_list", [])
                    if d.get("div_nm") in ("총합", "합계", "계")), None)
        if not tot:
            continue
        aff, adm = _f(tot.get("affc_zone")), _f(tot.get("administ_zone"))
        if aff is None and adm is None:
            continue
        out.append({
            "metric": iem,
            "affected": int(aff) if aff is not None else None,
            "total": int(adm) if adm is not None else None,
            "unit": item.get("unit", ""),
        })
    return out


def _hazard_exposure(
    board: str, emd_cd: str, sgg_cd: str, token: str, client: httpx.Client, cache: Optional[Cache]
) -> tuple:
    """영향범위 내 지표(인구·가구·주택·사업체) + scope. 읍면동 우선 — 일부 동/재해 500 → 시군구 폴백."""
    for code, scope in ((emd_cd, "읍면동"), (sgg_cd, "시군구")):
        ck = make_key("sgis_board", board, code)
        cached = cache.get(ck) if cache else None
        if cached is not None:
            rows = cached.get("rows", [])
        else:
            try:
                j = _get(client, f"ndsm/{board}", {"accessToken": token, "adm_cd": code})
            except SgisError:
                continue  # 읍면동 500 등 → 다음 단위로 폴백
            rows = j.get("result") if isinstance(j.get("result"), list) else []
            if cache:
                cache.set(ck, {"rows": rows})
        exposures = _board_exposures(rows)
        if exposures:
            return exposures, scope
    return [], ""


def _census_emd(lat: float, lon: float, token: str, client: httpx.Client) -> Optional[dict]:
    """좌표 → census 읍면동 {adm_cd(8자리), name}. 작은 bbox userarea cd=3."""
    cx, cy = to_utmk(lat, lon, token, client)
    j = _get(client, "boundary/userarea.geojson",
             {"accessToken": token, "cd": "3",
              "minx": cx - 30, "miny": cy - 30, "maxx": cx + 30, "maxy": cy + 30})
    for f in j.get("features", []):
        p = f.get("properties", {})
        if p.get("adm_cd"):
            return {"adm_cd": p["adm_cd"], "name": p.get("adm_nm", "")}
    return None


_HW_YEARS = (2025, 2024)       # 폭염특보 데이터 가용 = 최근 여름(실측, 2023 이전 없음)
_HW_MONTHS = (6, 7, 8, 9)      # 여름


def fetch_heatwave_history(
    sido: str,
    sigungu: str = "",
    *,
    years: tuple = _HW_YEARS,
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Optional[dict]:
    """최근 여름 폭염특보 발효 이력 (#86). 대지 시도/시군구 매칭, 해제 제외, 레벨별 발효일수.

    특보구역은 시도(상위)+구역(서울=권역·비서울=시군구). sido로 매칭, 시군구가 구역에 있으면 좁힘.
    숫자는 코드 규칙: API의 각 행 = 과거 폭염특보 1건(전부 '해제' 기록 = 종료된 특보). 레벨별로 센다.
    반환: {years, alert_count(경보), warning_count(주의보), scope, base_period, source, notes}.
    """
    if not sido:
        return None
    own = client is None
    client = client or httpx.Client(timeout=25.0)
    notes: List[str] = []
    try:
        token = get_token(client, cache)
        matched: List[dict] = []
        narrowed = False
        for y in years:
            for m in _HW_MONTHS:
                ck = make_key("sgis_heatwave", y, m)
                cached = cache.get(ck) if cache else None
                if cached is not None:
                    rows = cached.get("rows", [])
                else:
                    try:
                        j = _get(client, "ndsm/prevHwSpcnwsList.json",
                                 {"accessToken": token, "searchYear": str(y),
                                  "searchMonth": f"{m:02d}"})
                    except SgisError:
                        continue
                    rows = j.get("result") if isinstance(j.get("result"), list) else []
                    if cache:
                        cache.set(ck, {"rows": rows})
                # 시도 매칭
                sido_rows = [r for r in rows
                             if sido and sido[:2] in (r.get("up_spcnws_zone_nm") or "")]
                # 비서울 시군구가 구역명에 있으면 좁힘 (서울은 권역이라 시도 유지)
                if sigungu:
                    exact = [r for r in sido_rows if r.get("spcnws_zone_nm") == sigungu]
                    if exact:
                        sido_rows = exact
                        narrowed = True
                matched.extend(sido_rows)

        scope = sigungu if narrowed else f"{sido} 광역(권역)"
        if not matched:
            notes.append(f"폭염특보 기록 없음 ({sido} {min(years)}~{max(years)} 여름).")
        alert_count = sum(1 for r in matched if (r.get("spcnws_level_nm") or "") == "경보")
        warning_count = sum(1 for r in matched if (r.get("spcnws_level_nm") or "") == "주의보")
        return {
            "years": list(years),
            "alert_count": alert_count,
            "warning_count": warning_count,
            "scope": scope,
            "base_period": f"{min(years)}~{max(years)} 여름",
            "source": "sgis",
            "notes": notes,
        }
    finally:
        if own:
            client.close()


def fetch_site_hazards(
    lat: float,
    lon: float,
    *,
    dong_name: str = "",
    cache: Optional[Cache] = None,
    client: Optional[httpx.Client] = None,
) -> Optional[dict]:
    """대지 좌표 → 홍수·산사태 위험지도 영향범위 포함 여부. 실패 시 None (graceful).

    SGIS census 읍면동(8자리)을 얻어, 시군구(=앞5자리) 영향범위 읍면동 목록에 우리 동이
    들어있는지로 판정한다 (보간 아님 — 위험지도가 지정한 행정구역, 절대 원칙 1·3).
    dong_name: 표시용 읍면동명(없으면 SGIS adm_nm 사용).
    반환: {dong_name, emd_cd, sigungu_cd, flood{in_zone,affected_dong_count}, landslide{...},
          base_year, source, notes}.
    """
    own = client is None
    client = client or httpx.Client(timeout=25.0)
    notes: List[str] = []
    try:
        token = get_token(client, cache)
        emd = _census_emd(lat, lon, token, client)
        if not emd:
            return None
        emd_cd = emd["adm_cd"]
        sgg_cd = emd_cd[:5]
        label = dong_name or emd.get("name", "")
        base_year = ""

        out: dict = {
            "dong_name": label, "emd_cd": emd_cd, "sigungu_cd": sgg_cd,
            "source": "sgis", "notes": notes,
        }
        for key, (list_path, board_path, _title) in _HAZARDS.items():
            # ① 영향범위 읍면동 목록 → 대지 동 포함 여부 (동 단위 정밀 판정)
            ck = make_key("sgis_hazard", key, sgg_cd)
            cached = cache.get(ck) if cache else None
            if cached is not None:
                rows = cached.get("rows", [])
            else:
                try:
                    j = _get(client, f"ndsm/{list_path}", {"accessToken": token, "adm_cd": sgg_cd})
                except SgisError as e:
                    notes.append(f"{_title} 조회 실패: {e}")
                    out[key] = {"in_zone": None, "affected_dong_count": None,
                                "exposures": [], "exposure_scope": ""}
                    continue
                rows = j.get("result") if isinstance(j.get("result"), list) else []
                if cache:
                    cache.set(ck, {"rows": rows})
            affected_raw = {r.get("adm_cd") for r in rows if r.get("adm_cd")}
            # 위험목록 코드 길이가 census 8자리와 다를 수 있음 → 8자리 접두로 정규화해 비교
            # (그냥 emd_cd in affected 로 두면 포맷 불일치 시 '영향구역 아님'이라는 틀린 값을
            #  사실처럼 내보냄 = 절대 원칙 4 위반, 안전 데이터 false-negative).
            affected8 = {c[:8] for c in affected_raw}
            if affected_raw and any(len(c) != 8 for c in affected_raw):
                notes.append(f"{_title}: 위험목록 코드 길이가 8자리와 달라 앞 8자리로 매칭(참고).")
            if rows and rows[0].get("base_year"):
                base_year = rows[0]["base_year"]
            # ② 영향범위 내 지표(인구·가구·주택·사업체) (읍면동 우선·시군구 폴백)
            exposures, exp_scope = _hazard_exposure(
                board_path, emd_cd, sgg_cd, token, client, cache
            )
            out[key] = {
                "in_zone": emd_cd[:8] in affected8,
                "affected_dong_count": len(affected8),
                "exposures": exposures,
                "exposure_scope": exp_scope,
            }
        out["base_year"] = base_year
        return out
    finally:
        if own:
            client.close()


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

        # 반경 인구밀도(명/㎢) — 반경 원 면적 기준 (반경 내 실인구 / πr²). 참고용.
        area_km2 = math.pi * (radius / 1000.0) ** 2
        density_per_km2 = round(total_pop / area_km2) if area_km2 > 0 else None

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
            "density_per_km2": density_per_km2,
            "base_year": year,
            "source": "sgis",
            "notes": notes,
        }
    finally:
        if own:
            client.close()
