"""공동주택 대지 readout — 재건축·재개발·민간발주 공동주택 부지 종합 프로파일.

주소 1개 → 시군구 인문·경제 맥락을 한 화면에. 두 갈래 지표를 합친다:
  ① 기존 matrix 지표 (app.services.stats.collect_facts) — 고령·유소년·1인가구·순이동·세대수 등.
  ② 크랙한 다차원 census 지표 (getMeta ITM 차원해부) — 사업체수+산업구조·빈집·신혼부부·등록장애인.
모든 값은 KOSIS 시군구 실호출 (절대 원칙 1). 시군구 평균이라 '○○구 기준' 캐비엇 필수(절대 원칙 4).
유형 프리셋(재건축/재개발/민간/주상복합)은 *강조*만 바꾼다 — 데이터는 동일.

연구·데모 도구 (앱 코드 무수정). 검증되면 /readout 엔드포인트로 승격 가능.

사용:
    python scripts/demo_site_kosis.py --address "서울 서초구 잠원동 60-3" --type 재건축
    python scripts/demo_site_kosis.py --address "부산 수영구 남천동 23" --type 재개발
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx
from dotenv import load_dotenv

# 앱 서비스 재사용 (읽기 전용 호출). census 다차원은 정식 서비스 census_multidim 위임
# (동명 시군구 disambiguation·objL 순서 등 버그수정 단일 출처).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.resolve import resolve_address  # noqa: E402
from app.services import census_multidim, stats  # noqa: E402

# 크랙한 census 다차원 지표 (org, tbl, itm, prd주기, 단위, 라벨, 축).
CENSUS_INDICATORS = [
    {"key": "biz", "org": "101", "tbl": "DT_1BD1032", "itm": "T01", "prd": "년",
     "unit": "개", "label": "사업체수(활동)", "축": "산업·고용", "breakdown": True},
    {"key": "empty", "org": "101", "tbl": "DT_1JU1512", "itm": "ALL", "prd": "년",
     "unit": "호", "label": "빈집", "축": "주거"},
    {"key": "newly", "org": "101", "tbl": "DT_1NW1037", "itm": "ALL", "prd": "년",
     "unit": "쌍", "label": "신혼부부", "축": "주거수요"},
    {"key": "disabled", "org": "117", "tbl": "DT_11761_N009", "itm": "ALL", "prd": "년",
     "unit": "명", "label": "등록장애인", "축": "복지"},
]

# 유형별 강조 지표 (readout 프리셋). 데이터는 동일, 표시 강조만.
PRESET = {
    "재건축": {"고령인구비율", "빈집", "세대수", "순이동"},
    "재개발": {"빈집", "순이동", "1인가구비율", "고령인구비율"},
    "민간": {"신혼부부", "순이동", "사업체수(활동)", "유소년인구비율"},
    "주상복합": {"사업체수(활동)", "1인가구비율", "총인구수"},
}


def _key() -> str:
    load_dotenv()
    k = os.getenv("KOSIS_KEY")
    if not k:
        sys.exit("KOSIS_KEY 미설정 (.env 확인)")
    return k


def fetch_census(client, ind, city_name, sido):
    """크랙한 다차원 census 지표 1개 → (value, breakdown). 정식 서비스 위임 (버그수정 단일출처)."""
    data, _ = census_multidim.fetch_census_indicator(
        ind["org"], ind["tbl"], ind["itm"], city_name, ind["prd"],
        sido=sido, breakdown=ind.get("breakdown", False), client=client,
    )
    if not data:
        return None, None
    return data.get("value"), data.get("breakdown")


def main() -> None:
    ap = argparse.ArgumentParser(description="공동주택 대지 readout")
    ap.add_argument("--address", required=True)
    ap.add_argument("--use-type", default="주거", help="모드A 용도 (주거/상업/의료)")
    ap.add_argument("--type", default="재건축", choices=list(PRESET), help="프로젝트 유형(강조 프리셋)")
    args = ap.parse_args()

    _key()  # KOSIS_KEY 미설정이면 즉시 종료 (fail-fast)
    loc = resolve_address(args.address)
    emphasis = PRESET[args.type]

    print(f"\n{'=' * 64}")
    print(f"  공동주택 대지 readout — {args.type}  [{loc.address}]")
    print(f"  {loc.sigungu} 기준 (행안부 {loc.sgg_code}) · 좌표 {loc.lat:.4f},{loc.lon:.4f}")
    print(f"  ※ 모든 수치는 시군구 평균 — 대지 고유값 아님 (출처: KOSIS)")
    print(f"{'=' * 64}")

    # ① 기존 matrix 지표
    facts, notes, year = stats.collect_facts(loc.sgg_code, args.use_type)
    fact_map = {f["item"]: f for f in facts}
    print(f"\n[ 인구·가구 ]  (KOSIS {year})")
    for f in facts:
        star = " ★" if f["item"] in emphasis else "  "
        nat = f" (전국 {f['national_avg']}{f['unit']})" if f.get("national_avg") is not None else ""
        print(f"  {star}{f['item']:12} {f['value']:>12,}{f['unit']}{nat}" if isinstance(f["value"], (int, float))
              else f"  {star}{f['item']:12} {f['value']}{f['unit']}{nat}")

    # ② 크랙한 census 지표
    client = httpx.Client(timeout=25.0)
    census = {}
    try:
        print(f"\n[ 산업·주거·복지 ]  (KOSIS 시군구, 크랙 census)")
        for ind in CENSUS_INDICATORS:
            val, bd = fetch_census(client, ind, loc.sigungu, loc.sido)
            census[ind["key"]] = val
            star = " ★" if ind["label"] in emphasis else "  "
            if val is None:
                print(f"  {star}{ind['label']:12} — (해석 실패/무자료)")
                continue
            print(f"  {star}{ind['label']:12} {val:>12,}{ind['unit']}  [{ind['축']}]")
            if bd:
                print(f"       산업구조: " + " · ".join(f"{nm} {c:,}" for nm, c in bd[:4]))
    finally:
        client.close()

    # ③ 파생지표 (분모: 총인구·세대수)
    pop = fact_map.get("총인구수", {}).get("value")
    sed = fact_map.get("세대수", {}).get("value")
    print(f"\n[ 파생지표 ]")
    if pop and census.get("biz"):
        print(f"     사업체밀도   {census['biz'] / pop * 1000:>8.0f} 개/천명")
    if pop and census.get("disabled"):
        print(f"     장애인비율   {census['disabled'] / pop * 100:>8.1f} %")
    if sed and census.get("newly"):
        print(f"     신혼부부/세대 {census['newly'] / sed * 100:>8.1f} %")

    if args.type in ("민간",) :
        print(f"\n  ⚠ 택지·신도시 신축이면 시군구 평균이 '형성 전 신규단지'를 못 반영 — 배후 규모 참고용.")
    print()


if __name__ == "__main__":
    main()
