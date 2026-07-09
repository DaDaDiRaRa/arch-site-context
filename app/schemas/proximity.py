"""S1 — 데이터 근접도 레이어 (CLAUDE.md §8.11).

모든 fact/signal 이 "이 수치가 대지에 얼마나 가까운 단위에서 나왔나"를 한 축으로 말한다:

    대지(필지) > 반경 > 읍면동 > 시군구 > proxy(추정)

이 등급은 **순수 메타데이터**다 — 새 숫자를 만들지 않고, 기존 scope_level(자유문자열)을
정규화만 한다. LLM 0·환각 0 (절대 원칙 1·2). 차별점의 핵심("시군구 평균은 대지값이 아님",
절대 원칙 4)을 모든 출력에 **기계가독·정렬가능**하게 박는다.

주의: 근접도는 *지리적 해상도*이지 지표 품질이 아니다. proxy 는 "실제 지역질의 없이 추정/보간한
값"을 뜻하며, 우리 앱은 보간을 금지(원칙 1·3)하므로 현재 producer 는 거의 없다 — 등급은 완결성을
위해 정의해 둔다. (문화시설 수요를 생산가능인구비율로 대신하는 것처럼 '대리 지표'인 경우는 지표
품질 문제이지 근접도가 아니므로 여기서 proxy 로 낮추지 않는다.)
"""

from __future__ import annotations

from typing import Literal, Optional

# 대지에 가까운 순 (best → worst). 정렬·비교의 단일 기준.
Proximity = Literal["대지", "반경", "읍면동", "시군구", "proxy"]

PROXIMITY_ORDER: list = ["대지", "반경", "읍면동", "시군구", "proxy"]
_RANK = {p: i for i, p in enumerate(PROXIMITY_ORDER)}

# scope_level(자유문자열) → 정규화된 proximity 등급.
# scope_level 값은 코드가 통제하지만(반경/읍면동/시군구), 표기 흔들림에 대비해 별칭도 매핑.
_SCOPE_LEVEL_MAP = {
    "대지": "대지", "필지": "대지",
    "반경": "반경",
    "읍면동": "읍면동", "행정동": "읍면동", "동": "읍면동",
    "시군구": "시군구", "구": "시군구", "군": "시군구", "시": "시군구",
    "proxy": "proxy", "추정": "proxy",
}


def proximity_of(scope_level: Optional[str]) -> Optional[str]:
    """scope_level → proximity 등급. 알 수 없거나 비면 None (억지로 채우지 않음, 절대 원칙 3)."""
    if not scope_level:
        return None
    return _SCOPE_LEVEL_MAP.get(scope_level)


def proximity_rank(p: Optional[str]) -> int:
    """정렬용 정수 (작을수록 대지에 가까움). 알 수 없으면 최하위."""
    return _RANK.get(p, len(PROXIMITY_ORDER))
