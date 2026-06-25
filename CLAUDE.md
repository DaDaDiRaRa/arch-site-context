# CLAUDE.md — arch-site-context (터읽기)

> Claude Code는 이 레포에서 작업할 때 이 문서를 먼저 읽고, 여기 적힌 아키텍처·원칙·완료기준을 따른다.
> 한 번에 한 Phase씩. 각 Phase의 "완료 기준"을 만족하기 전에는 다음으로 넘어가지 않는다.

---

## 1. 이 앱이 무엇인가

**대지 주소만 넣으면, 그 동네가 어떤 곳인지 두 방식으로 읽어주는 웹앱.**
건축가가 설계 시작 전에 만드는 '대지 분석 보드'의 인문·주변 파트를 자동으로 채운다.

- **모드 A — 지역 통계**: 주소 + 건물 용도 → 그 지역의 인구·세대·경제·고령화 등 통계를 *용도에 맞는 것만* 골라 → 표 + 참고 시사점 + 한 문단 초안.
- **모드 B — 주변 시설**: 주소 + 시설종류 + 반경(500/1000/2000m) → 반경 내 시설 목록·개수 + 위성사진에 핀·반경 찍은 PNG.

쉬운 비유: "신입이 반나절 걸려 하던 대지 주변조사를, 주소 한 줄로 표·문단·지도까지." 단, 최종 설계 판단은 사람이 한다.

이름: 레포 `arch-site-context` / 팀 호칭 **터읽기**.

---

## 2. 절대 원칙 (이 앱의 존재 이유)

이걸 어기면 "그냥 비싼 ChatGPT 래퍼"가 된다. 차별점은 전적으로 여기서 나온다.

1. **추출, 해석하지 않는다** — 값은 실제 API(KOSIS·카카오)에서 *호출해 가져온다*. AI 기억·추정 금지.
2. **숫자는 코드·규칙, 표현만 AI** — facts(수치)와 implications(함의)는 코드/룩업이 만든다. LLM은 마지막 '한 문단'만.
3. **확인 불가 하드블록** — 데이터로 답할 수 없으면 추정하지 말고 "확인 불가"로 멈춘다. 환각 금지.
4. **출처·기준 명시** — 모든 수치에 출처(통계표ID/API)·기준연도. 통계는 시군구 평균이므로 출력에 **'○○구 기준'** 항상 표기 (대지 고유값 아님).
5. **판단은 사람** — 좋다/나쁘다·사업성 단정 금지. 재료와 근거만 제시.
6. **모델은 Claude 하나** — 교차검증·다중모델 금지 (정답이 정해진 데이터엔 잡음만 는다).
7. **설정은 JSON, 코드 아님** — 용도별 목록(matrix.json)·함의 규칙(implications.json)은 외부 JSON. 건축가가 코드 없이 수정. (팀 자산·bus-factor)

### 차별점 체크리스트 (기능 추가 시 게이트)
새 기능이 "그냥 범용 AI에 붙여넣어도 되는 것"이면 빼거나 재설계한다. 우리만 되는 것에 집중:
- [ ] 실제 API를 호출하는가? (기억이 아니라)
- [ ] 좌표·거리·이미지 등 코드만 할 수 있는 계산인가?
- [ ] 출처·기준연도가 붙는가?
- [ ] 데이터 밖이면 '확인 불가'로 멈추는가?
- [ ] 결과가 항상 같은 형식이라 팀이 재사용 가능한가?

---

## 3. 시장 포지션 (왜 만드나)

기존 도구는 전부 **돈·규제·물리**에 몰려 있고 **사람·생활맥락** 칸은 비어 있다.
- 한국: 닥터빌드 AiCON·빌드잇 = 사업수지·인허가·설계안 생성.
- 해외: TestFit = 사업성/수익률, Autodesk Forma = 일조·바람·소음 환경분석, Giraffe = GIS·컴플라이언스.
- **빈칸 = 공모(설계경기) 대지분석 보드의 인문·생활 파트** → 우리 자리.

우리가 **안 만드는 것** (경계): 일조·바람·매싱(=Forma/모델링 트랙), 사업수지·분양가(=닥터빌드). 좁게 "공모용 인문·생활 맥락 + 수급 진단"만 깊게.

---

## 4. 기술 스택 · 환경

- 백엔드: FastAPI (Python 3.11), 프론트: React + Vite + Tailwind
- 배포: GCP Cloud Run + Secret Manager(키) + GCS(캐시 버킷)
- **MCP 아님** — 순수 FastAPI HTTP 엔드포인트. (파이프라인 연결은 나중에 project_seed JSON)
- 로컬: Windows, 프로젝트 `D:\APPS\arch-site-context`. **venv는 풀경로로 생성, Microsoft Store python 금지.**
- 키(.env, 절대 커밋 금지): `KAKAO_KEY`, `VWORLD_KEY`, `KOSIS_KEY`, (선택)`VWORLD_REFERER`, `ANTHROPIC_API_KEY`

### 외부 API
- **카카오 로컬**: 주소→좌표, 키워드 반경검색 (모드 B)
- **VWorld**: 항공영상 타일 `https://api.vworld.kr/req/wmts/1.0.0/{KEY}/Satellite/{z}/{y}/{x}.jpeg` (jpeg). 키가 도메인 잠금일 수 있음 → 안 되면 카카오 스카이뷰로 폴백.
- **KOSIS OpenAPI**: 지역 통계 (모드 A). HTTPS 필수, 분당 호출 제한 있음 → 캐시 우선.
- **Claude API**: 한 문단 서술 1회 (모드 A P6).

---

## 5. 아키텍처 (흐름 = 서버 함수 = 엔드포인트)

```
[모드 B]  주소 → resolve_coord(카카오) → search_facilities(반경) → distance(하버사인)
              → counts(반경밴드 집계)              → /facilities
              → compose_map(VWorld타일+핀+원+범례) → /facilities/map (PNG)

[모드 A]  주소 → resolve_region(시군구+읍면동코드) → select_items(matrix.json)
              → fetch_stats(KOSIS+캐시) → facts[]
              → derive_implications(implications.json, 규칙) → implications[]
              → compose_narrative(Claude 1회 + 규칙 폴백)    → /analyze
```

### 엔드포인트
| 메서드 | 경로 | 모드 | 역할 |
|---|---|---|---|
| POST | `/facilities` | B | 반경 시설 목록·개수 |
| POST | `/facilities/map` | B | 위성 PNG (핀·반경) |
| POST | `/analyze` | A | 지역 통계 + 함의 + 문단 |
| GET | `/matrix` | A | 용도별 항목 목록 (투명성) |
| GET | `/health` | - | 헬스체크 |
| (P9+) | `/compare`,`/ask` | - | 비교 / 물어보기 (나중) |

---

## 6. 데이터 계약 (스키마) — 코드보다 먼저 확정

```jsonc
// FacilityResult (모드 B)
{
  "center": {"lat": 0, "lon": 0, "address": "..."},
  "results": [{"kind":"어린이집","name":"...","lat":0,"lon":0,"dist_m":420,"radius_band":"500"}],
  "counts": {"500":{"어린이집":3,"경로당":5}, "1000":{...}, "2000":{...}},
  "source": "kakao", "base_date": "2026-06-25"
}

// RegionStat (모드 A)
{
  "region": {"name":"영등포구","code":"11560","resolution":"시군구"},
  "year": 2024, "use_type": "주거",
  "facts": [{"item":"1인가구비율","value":38.2,"national_avg":33.4,"unit":"%","source_tbl":"DT_1...","year":2024}],
  "implications": [{"text":"소형 평형·공유공간 검토","basis":"1인가구비율","tag":"참고"}],
  "draft_paragraph": "...",
  "source": "ai"   // 또는 "rule_based_fallback"
}

// ErrorBlock (데이터 없을 때 하드블록)
{ "code":"NO_DATA", "message":"제공된 데이터로는 확인 불가" }
```

### 설정 파일 (외부 JSON, 건축가 편집)
```jsonc
// app/data/matrix.json — 용도별 KOSIS 항목
{"주거":[{"item":"1인가구비율","tbl_id":"DT_1...","priority":1,"min_resolution":"읍면동","freq":"5년"}]}

// app/data/implications.json — 함의 규칙
[{"when":{"item":"고령인구비율","op":">","vs":"national","margin":5},
  "use_types":["주거","의료","문화"],"then":"무장애 동선·휴게공간 검토","tag":"참고"}]
```

---

## 7. 전체 로드맵

| 묶음 | Phase | 내용 | 상태 |
|---|---|---|---|
| **모드 B** (먼저) | P0 | 골격 + 스키마 (스텁) | ✅ 완료 |
| | P1 | 반경 시설 검색 (카카오) | ✅ 완료 |
| | P1.5 | 카카오 45건 상한 회피 (bbox 적응분할) | ✅ 완료 |
| | P1.5b | 공공데이터 경로당 등 공식시설 보강 | ⏸ 보류 (§8.5) |
| | P1.6 | 주소해석 견고화 (카카오+JUSO, 법정동코드) | ✅ 완료 |
| | P2 | VWorld 타일 게이트 | ✅ 완료 (VWorld 확정, Referer 불필요) |
| | P3 | 위성 PNG (핀·반경원·범례·축척·출처) | ✅ 완료 |
| **모드 A** | P4 | 용도별 목록 + 함의 룩업 (JSON) | ✅ 완료 (설정·로직, KOSIS는 P5) |
| | P5 | KOSIS 실조회 + 캐시 | ✅ 완료 (연령구조 5지표, 캐시 0콜. 일부 지표 §8.6) |
| | P6 | 한 문단 서술 + 폴백 | ✅ 완료 (Claude 1회, AI/규칙 폴백 둘 다 facts 보존) |
| **합치기** | P7 | 프론트 — A·B 탭 한 화면 | ✅ 완료 (React+Vite+Tailwind, dev 프록시 연결) |
| | P8 | Cloud Run 배포 | |
| **나중 확장** | P9 | 정렬·필터·여러 후보지 비교 | 자리만 |
| | P10 | '물어보기' 모드 (데이터 위에서만) | 자리만 |
| | P11 | 수급 진단 (A×B 교차) ★간판기능 | 자리만 |

### 진행 규칙
- **한 번에 한 Phase.** 완료 기준 통과 후 다음.
- P0 끝나면 스키마를 사람이 검토.
- P2(VWorld)에서 막히면 멈추고 카카오 스카이뷰로 폴백 판단.
- "경로당" 등 비상업 시설 공공데이터 보강은 §8.5에 보류 기록. data.go.kr 키 등록되면 착수.
- 막히면 추정으로 때우지 말고 멈춘다.

---

## 8. P11 — 수급 진단 (간판 기능, 나중) 메모

A(인구 수요) × B(시설 공급)를 교차해 "이 동네 무엇이 부족/과잉한가"를 근거와 함께 제시.
예: "반경 1km 어린이집 2개 + 영유아가구 비율 전국평균 +8%p → 보육시설 수요 대비 공급 부족(참고)".
시장에 없는 조합. A·B 둘 다 있어야 가능 → 우리 구조에서만 나온다. 단 '부족/과잉'은 휴리스틱이므로 '참고' 태그 + 판단은 사람.

---

## 8.5 P1.5b — 공공데이터 시설 보강 (보류 메모)

비상업 시설(경로당·마을회관 등)은 카카오 키워드에 누락될 수 있어 정부 공식 데이터로 보강한다.
**지금은 보류** — `DATA_GO_KR_API_KEY`가 `code 30 (SERVICE KEY IS NOT REGISTERED)`. 데이터셋 활용신청·전파 후 착수.

### 확정된 것 (재조사 불필요)

- 엔드포인트: `https://api.data.go.kr/openapi/tn_pubr_public_vill_hall_sen_cent_api` (전국마을회관및경로당표준데이터, data 15114136)
- 응답 필드: `FLCT_NM`(시설명) · `LAT`(위도) · `LOT`(경도) · `LCTN_ROAD_NM_ADDR`(도로명) · `LCTN_LOTNO_ADDR`(지번) · `BUSI_COD_NM`(영업상태)
- 요청: `serviceKey, pageNo, numOfRows(≤1000), type=json`. 지역 필터 파라미터는 미확인 → 전국 페이징 후 bbox/하버사인 필터 + 캐시 필요.

### 끼우는 지점 (구조 변경 최소 — 복잡하지 않음)

1. 새 모듈 `app/services/gov_data.py` 에 `fetch_govt(kind, bbox)` 추가 (네트워크·캐시·필터는 이 안에 격리).
2. `services/facilities.py` 의 kind 루프에서 카카오 docs 뒤에 gov docs를 **이어붙이기만** 하면 됨 — 기존 중복제거(이름+좌표)·밴드·counts 파이프라인이 그대로 처리.
3. 스키마: `Facility`에 `src: str = "kakao"` 1개 추가(하위호환). 최상위 `source`는 `"kakao"` → `"kakao+gov"`.
4. 키 미등록(code 30)이면 카카오만 쓰고 `notes`에 "경로당 공식데이터 미연결" 정직 표시 (graceful, 절대 원칙 3·정직성).

> 즉 오케스트레이터는 한 줄(이어붙이기) + 스키마 1필드. 유일한 실작업은 `gov_data.py` 내부의
> 전국 데이터 지역 필터링·캐싱이며 다른 코드로 새지 않는다. 키만 풀리면 빠르게 완성 가능.

---

## 8.6 P5 KOSIS — 확정/미확정 지표 메모

KOSIS 키 동작 확인. 지역코드(objL1) = resolve 의 sgg_code 와 정확히 일치 (검증됨).

### 확정 테이블 (실데이터 흐름)

- `DT_1B04005N` 행정구역(시군구)별/5세별 주민등록인구 (orgId 101, itmId T2, objL2=연령밴드 ALL).
  C2코드 = 밴드시작나이+5 (`5`=0-4세 … `70`=65-69세 … `105`=100+, `0`=계). 전국 = C1 `00`.
- 여기서 계산하는 5지표(한 테이블 1콜): 총인구수(direct) · 고령인구비율 · 유소년인구비율 ·
  생산가능인구비율(age_share) · 노년부양비(age_dependency). 계산 레시피는 `services/stats.py`.

### 미확정 지표 (matrix.json `method:"unconfirmed"` — 추정 않고 건너뜀)

- 1인가구비율·평균가구원수(인구주택총조사) · 인구밀도(면적 결합) · 사업체수·종사자수(전국사업체조사) ·
  주택보급률·주간인구지수. → 각 KOSIS (orgId/tblId/itmId) 확정되면 matrix.json 에 채우면 끝
  (코드 변경 불필요). 메타 API 는 포맷 달라 막혔으므로, 데이터 응답(itmId=ALL,objL=ALL)에서 코드 역추출.

### 캐시

- `services/cache.py` Cache 인터페이스(get/set) + FileCache(out/kosis_cache). GCS 교체 가능.
  키 = (orgId,tblId,지역,연도,objL2,itmId). 동일요청 재호출 0콜 확인.
