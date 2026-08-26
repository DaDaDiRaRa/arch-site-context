"""답변 수치 무결성 백스톱 — LLM 답변이 '우리가 보여준 숫자'만 쓰는지 코드로 검사.

`/ask` 의 그라운딩은 지금까지 전적으로 프롬프트 규칙에 의존했다(모델이 스스로 '확인 불가'라고
선언했는지만 봤다). 모델이 확신에 차서 틀린 숫자를 쓰면 그대로 '데이터 기반'으로 나갔다.
이 모듈은 그 마지막 한 겹을 코드로 막는다 (절대 원칙 1·2·3).

**허용 풀의 정의 = 우리가 프롬프트로 보낸 텍스트에 등장한 숫자 전부.**
번들 스키마를 훑어 값만 모으는 방식이 아니다 — 항목명에 숫자가 박혀 있고(`1인가구비율`·
`65세 이상`·`0-4세`), 수급진단 `note`·`signal` 의 자유서술에도 숫자가 들어가서(`반경 1000m 내
… 23개`) 값만 모으면 전부 오탐이 된다. 계약이 "준 숫자만 써라" 이므로 풀의 정의를 계약과
같은 자리(= 실제로 보낸 텍스트)에 둔다. 정의가 한 줄이라 감사도 된다.

예외는 하나 — **식별자 안의 숫자**(`DT_1B04005N` 의 `1`·`04005`)는 수량이 아니라 이름의
일부라 양쪽(풀·검사)에서 똑같이 뺀다. 규칙이 "앞이 영문자·밑줄이면 건너뛴다" 한 줄이라
정의의 감사 가능성은 유지된다. 실측에서 모델이 출처표ID를 인용하자 '검증한 수치 5개' 중
2개가 표ID 조각이던 것을 보고 넣었다(빼지 않으면 검증 개수가 거짓으로 부푼다).

⚠ **이건 사실검증기가 아니다.** 잡는 것은 오직 "답변에 제공 데이터에 없는 숫자가 있는가" 하나뿐.
설계상 범위 밖(=못 잡음):
- 숫자가 아닌 환각 — 없는 시설명·지명, 잘못된 인과관계 서술
- 항목↔값 짝짓기 오류 — 고령인구 값을 유소년인구라고 라벨하는 경우. 풀 안의 숫자라 통과한다.
  잡으려면 답변에서 (항목, 값) 쌍을 추출해야 하는데 한국어 문장 파싱 신뢰도가 낮아 오탐이 더 크다.
이름을 '수치 무결성'으로 붙여둔다 — 나중에 이 검사가 과대평가되지 않도록.
"""

from __future__ import annotations

import re
from typing import List, Set, Tuple

#: 천단위 콤마·소수 허용. '8.3%'·'1,234명'·'2025년'·'1인가구' 전부 토큰으로 잡힌다.
#: 단, **앞이 ASCII 영문자·밑줄이면 식별자 조각**으로 보고 건너뛴다 —
#: `DT_1B04005N` 의 `1`·`04005`, `PM2.5` 의 `2.5` 같은 것. 수량이 아니라 이름의 일부다.
#: ★ lookbehind 에 숫자·소수점(`\d.`)도 넣어야 한다: 영문자만 배제하면 `04005` 를 건너뛴 뒤
#: 엔진이 한 칸 전진해 `4005` 를 다시 잡는다(실측 — 앞이 `0` 이라 lookbehind 를 통과해 버림).
#: 토큰은 항상 진짜 경계에서 시작해야 한다.
#: 실측(2026-08-26)에서 모델이 출처표ID를 인용하자 checked 가 표ID 조각으로 부풀어
#: "수치 5개 검증"의 2개가 표ID였다 — 세는 대상이 아니면 풀에도 넣지 않는다(양쪽 일관).
#: `2km`·`1인가구` 처럼 **뒤에** 글자가 붙는 건 단위·이름 접미라 정상 토큰으로 남긴다
#: (그래야 단위 변환 '2km' 를 잡을 수 있다).
_NUM = re.compile(r"(?<![A-Za-z_\d.])(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")

#: 부동소수 반올림 비교 오차 (round(8.35,1) 같은 이진표현 흔들림 흡수)
_EPS = 1e-9


def _tokens(text: str) -> List[str]:
    return _NUM.findall(text or "")


def _value(token: str) -> float:
    return float(token.replace(",", ""))


def _decimals(token: str) -> int:
    return len(token.split(".")[1]) if "." in token else 0


def allowed_pool(prompt_text: str) -> Set[float]:
    """프롬프트로 실제 보낸 텍스트 → 인용 허용 숫자 집합.

    ★ 재시도 시에도 **최초 프롬프트 기준으로 한 번만** 만들어야 한다 — 교정 메시지에 위반
    수치를 적어 보내므로, 그때 다시 만들면 방금 잡은 환각이 풀에 들어가 버린다.
    """
    return {_value(t) for t in _tokens(prompt_text)}


def check_numbers(answer: str, pool: Set[float]) -> Tuple[List[str], List[str]]:
    """(답변에서 검사한 수치 토큰, 그중 풀에 없던 토큰).

    반올림은 허용한다 — '약 8%'(← 8.3)는 새 숫자가 아니라 같은 값의 표현이다. 답변 토큰의
    소수 자릿수로 풀 값을 반올림해 일치하면 통과. 반대로 **파생 산술(차이·배수)과 단위 변환
    (1000m→1km, 만 단위)은 통과하지 못한다** — 그 둘은 프롬프트에서 금지한다(원칙 2:
    LLM 은 새 숫자를 만들지 않는다). 여기서 걸리면 규칙 위반이 맞다.
    """
    checked: List[str] = []
    unverified: List[str] = []
    for token in _tokens(answer):
        if token in checked:
            continue
        checked.append(token)
        value, digits = _value(token), _decimals(token)
        if any(abs(round(p, digits) - value) < _EPS for p in pool):
            continue
        unverified.append(token)
    return checked, unverified


def verify(text: str, prompt_text: str) -> Tuple[bool, List[str]]:
    """(통과 여부, 미검증 토큰) — 풀 생성 + 검사를 한 번에.

    `/ask` 처럼 checked 목록까지 노출할 필요 없이 "쓸 수 있나"만 알면 되는 호출부용
    (narrative P6 · synthesis S4). 그쪽은 실패 시 **이미 있는 규칙 기반 폴백**으로 떨어지므로
    교정 재요청 없이 즉시 판정만 하면 된다 — `/ask` 는 폴백이 없어(차단하면 답 전체를 잃음)
    재시도를 한 번 두는 것과 대비된다.
    """
    _checked, unverified = check_numbers(text, allowed_pool(prompt_text))
    return (not unverified), unverified
