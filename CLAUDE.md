# CLAUDE.md — arch-site-context (터읽기)

> Claude Code는 이 레포에서 작업할 때 이 문서를 먼저 읽고, 여기 적힌 아키텍처·원칙·완료기준을 따른다.
> 한 번에 한 Phase씩. 각 Phase의 "완료 기준"을 만족하기 전에는 다음으로 넘어가지 않는다.

---

## 1. 이 앱이 무엇인가

**대지 주소만 넣으면, 그 동네가 어떤 곳인지 여러 방식으로 읽어주는 웹앱.**
건축가가 설계 시작 전에 만드는 '대지 분석 보드'의 인문·주변 파트를 자동으로 채운다.

기본 두 모드 위에, 둘을 교차·확장한 세 기능이 더 있다(P9~P11 완료):

- **모드 A — 지역 통계**: 주소 + 건물 용도 → 그 지역의 인구·세대·경제·고령화 등 통계를 *용도에 맞는 것만* 골라 → 표 + 참고 시사점 + 한 문단 초안.
- **모드 B — 주변 시설**: 주소 + 시설종류 + 반경(500/1000/2000m) → 반경 내 시설 목록·개수 + 위성사진에 핀·반경 찍은 PNG.
- **수급진단 (P11, ★간판)**: A(인구 수요)×B(시설 공급) 교차 → "무엇이 부족/과잉인가"를 근거+'참고'로. 시장에 없는 조합 — A·B 둘 다 있어야 가능.
- **후보지 비교 (P9)**: 여러 대지를 한 번에 A·B·수급진단으로 나란히 + 컬럼 정렬. 종합점수는 안 매김(판단은 사람).
- **물어보기 (P10)**: 위 데이터 *위에서만* 자연어 질문에 답. 데이터 밖이면 '확인 불가'로 멈추고, 사용자가 켤 때만 웹검색(외부·참고) 폴백.

쉬운 비유: "신입이 반나절 걸려 하던 대지 주변조사를, 주소 한 줄로 표·문단·지도·진단·비교까지." 단, 최종 설계 판단은 사람이 한다.

**분석 범위 (P12 이후 확장 방향)**: 인문·생활 맥락(인구·시설·수급)에서 출발해, 환경(대기·소음·토양), 안전(재해·범죄), 부동산(실거래가·공시지가), 건축·도시계획(문화재·토지이용규제·재해위험), 교통·접근성, 교육·의료·복지까지 확장. 전부 "수치+출처+재현 가능" 원칙 안. 총 약 161개 소스 목록은 `API_MASTER_LIST.md` 참조.

이름: 레포 `arch-site-context` / 팀 호칭 **터읽기**.

---

## 2. 절대 원칙 (이 앱의 존재 이유)

이걸 어기면 "그냥 비싼 ChatGPT 래퍼"가 된다. 차별점은 전적으로 여기서 나온다.

1. **추출, 해석하지 않는다** — 값은 실제 API(KOSIS·카카오)에서 *호출해 가져온다*. AI 기억·추정 금지.
2. **숫자는 코드·규칙, 표현만 AI** — facts(수치)·implications(함의)·수급 signal은 코드/룩업이 만든다. LLM은 *표현*만 담당한다: 모드 A 한 문단 서술(P6), 물어보기 답변(P10, 우리 데이터 위에서만). 새 숫자를 만들지 않는다.
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

우리가 **안 만드는 것** (경계):

- **물리 시뮬레이션**: 일조·바람·그림자·매싱 계산 (=Autodesk Forma 트랙)
- **재무 분석**: 사업수지·분양가·NPV (=닥터빌드 트랙)
- **규제 해석**: "이 용도지역에 뭘 지을 수 있는가" 판단 → 우리는 규제 *사실*만 제시, 해석은 사람

우리가 **하는 것** (P12 이후 확장 포함):

- 규제 사실을 수치로 제시 (문화재보호구역 반경 포함 여부, 재해위험 등급 등)
- 환경·안전·부동산·교통·교육·의료 데이터를 수급진단에 연결
- 건축가가 설계 판단하기 위한 재료 전부 — 해석·단정은 안 함

---

## 4. 기술 스택 · 환경

- 백엔드: FastAPI (Python 3.11), 프론트: React + Vite + Tailwind
- 배포: GCP Cloud Run + Secret Manager(키) + GCS(캐시 버킷)
- **MCP 아님** — 순수 FastAPI HTTP 엔드포인트. (파이프라인 연결은 나중에 project_seed JSON)
- 로컬: Windows, 프로젝트 `D:\APPS\arch-site-context`. **venv는 풀경로로 생성, Microsoft Store python 금지.**
- 키(.env, 절대 커밋 금지): `KAKAO_KEY`, `JUSO_API_KEY`(주소 폴백·현재 dev키), `VWORLD_KEY`, `KOSIS_KEY`, `ANTHROPIC_API_KEY`, (선택)`VWORLD_REFERER`, (보류)`DATA_GO_KR_API_KEY`(경로당 보강·§8.5)
- **추가 예정 키**: P12 이후 단계적 발급. 전체 소스 목록·키 상태·우선순위는 **`API_MASTER_LIST.md`** 참조 (약 161개 소스, ✅기존키/🔑새키/💰유료/⚠️제한 구분).

### 외부 API

- **카카오 로컬**: 주소→좌표, 키워드 반경검색 (모드 B)
- **JUSO(행안부 도로명주소)**: 카카오 주소검색 0건 시 정규화·법정동코드 폴백 (P1.6)
- **VWorld**: 항공영상 타일 `https://api.vworld.kr/req/wmts/1.0.0/{KEY}/Satellite/{z}/{y}/{x}.jpeg` (jpeg). 키가 도메인 잠금일 수 있음 → 안 되면 카카오 스카이뷰로 폴백.
- **KOSIS OpenAPI**: 지역 통계 (모드 A). HTTPS 필수, 분당 호출 제한 있음 → 캐시 우선.
- **Claude API**: ① 한 문단 서술 1회 (모드 A P6) ② 물어보기 그라운디드 답변 (P10) ③ 물어보기 웹검색 폴백 — Claude 내장 `web_search` 서버툴 (P10, opt-in. 모델은 Claude 하나 유지 — 원칙 6).

---

## 5. 아키텍처 (흐름 = 서버 함수 = 엔드포인트)

```text
[모드 B]  주소 → resolve_coord(카카오) → search_facilities(반경) → distance(하버사인)
              → counts(반경밴드 집계)              → /facilities
              → compose_map(VWorld타일+핀+원+범례) → /facilities/map (PNG)

[모드 A]  주소 → resolve_region(시군구+읍면동코드) → select_items(matrix.json)
              → fetch_stats(KOSIS+캐시) → facts[]
              → derive_implications(implications.json, 규칙) → implications[]
              → compose_narrative(Claude 1회 + 규칙 폴백)    → /analyze

[P11 수급]  주소 → A수요(facts) + B공급(반경 counts)
              → cross_rules(supply_demand.json 임계값) → 진단[]  → /diagnose

[P9 비교]   주소 N개 → 각 후보지 gather_bundle(A·B·P11) → 나란히  → /compare
              (후보지당 resolve·시설검색 1회, 실패 격리)

[P10 물어보기] 주소+질문 → gather_bundle(A·B·P11) → answer_grounded(Claude, 데이터 위에서만)
              → 데이터 밖이면 '확인 불가'; web=true 면 web_search 폴백(외부·참고) → /ask
```

### 엔드포인트

| 메서드 | 경로 | 모드 | 역할 |
| --- | --- | --- | --- |
| POST | `/facilities` | B | 반경 시설 목록·개수 |
| POST | `/facilities/map` | B | 위성 PNG (핀·반경) |
| POST | `/analyze` | A | 지역 통계 + 함의 + 문단 |
| GET | `/matrix` | A | 용도별 항목 목록 (투명성) |
| POST | `/diagnose` | P11 | 수급진단 (A수요×B공급 교차) ★간판 |
| POST | `/compare` | P9 | 여러 후보지 A·B·P11 나란히 비교 |
| POST | `/ask` | P10 | 물어보기 (데이터 위에서만 + 웹검색 opt-in 폴백) |
| POST | `/site` | P14 | 대지 기본정보 (개별공시지가=VWorld·실거래·건축물대장). 공시지가는 data.go.kr 미승인 → VWorld `LP_PA_CBND_BUBUN` 우회 |
| POST | `/seed` | P14 | 보드 합본 진입점 — 공유 site(좌표·pnu) + context(상권·학교·어린이집·문화시설·부동산지수·날씨·생활인구·공연시설). `schemas/project_seed.ProjectSeed`. law·knowledge는 형제앱 자리(INTEGRATION) |
| GET | `/health` | - | 헬스체크 |

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

// DiagnoseResult (P11) — 전체 정의는 app/schemas/diagnose.py
{
  "center":{...}, "region":{...}, "radius":1000,
  "diagnoses":[{"name":"보육시설 수급",
    "demand":{"item":"유소년인구비율","value":8.3,"national_avg":10.3,"unit":"%","level":"낮음","source_tbl":"...","year":2025},
    "supply":{"kinds":["어린이집","유치원"],"count":23,"radius":1000,"level":"많음","capacity":2785,"capacity_scope":"영등포구"},
    "signal":"수요 낮음·공급 많음","note":"...","tag":"참고"}],
  // capacity = 시군구 어린이집 정원(정보공개포털 cpmsapi021, capacity_source:"childcare"). 반경 개수와 단위 다름·참고.
  "source":"kakao+kosis", "base_date":"...", "notes":[]
}

// CompareResult (P9) — app/schemas/compare.py
{ "use_type":"주거","radius":1000,"kinds":["어린이집","경로당"],
  "sites":[{"address":"...","region":{...},"facts":[...],"counts":{"어린이집":21},
            "diagnoses":[...],"error":null,"notes":[]}],   // 후보지 실패는 error 격리
  "base_date":"..." }

// AskResult (P10) — app/schemas/ask.py. 답은 동봉된 번들 위에서만 (투명성)
{ "question":"...","answer":"...","answerable":true,
  "source":"ai",          // ai(그라운디드) | ai_web(외부폴백) | no_data | ai_unavailable
  "region":{...},"facts":[...],"counts":{...},"diagnoses":[...],
  "web_sources":[{"title":"...","url":"..."}], "base_date":"...","notes":[] }
```

### 설정 파일 (외부 JSON, 건축가 편집)

```jsonc
// app/data/matrix.json — 용도별 항목 목록 (P12 이후 멀티소스로 확장)
//   source_type: "kosis" | "airkorea" | "data_go_kr" | "molit" | ...  (P12에서 필드 추가 예정)
//   method: direct | age_share | age_dependency | ratio | unconfirmed
//   region_scheme: reg(행안부코드, 기본) | census(통계청코드 역추출, §8.6)
//   현재는 KOSIS 항목만; 에어코리아·건축물대장·실거래가 등은 source_type 구분으로 동일 구조 관리
{"주거":[
  {"item":"고령인구비율","method":"age_share","age_min":65,
   "kosis":{"orgId":"101","tblId":"DT_1B04005N","itmId":"T2","objL2":"ALL"},
   "priority":1,"min_resolution":"시군구","freq":"1년","unit":"%"},
  {"item":"1인가구비율","method":"ratio","region_scheme":"census",
   "kosis":{"orgId":"101","tblId":"DT_1JC1511","num_itm":"T210","den_itm":"T100","objL2":"000","objL2_pick":"000"},
   "priority":1,"min_resolution":"시군구","freq":"1년","unit":"%"}
]}

// app/data/implications.json — 함의 규칙
[{"when":{"item":"고령인구비율","op":">","vs":"national","margin":5},
  "use_types":["주거","의료","문화"],"then":"무장애 동선·휴게공간 검토","tag":"참고"}]

// app/data/supply_demand.json — P11 수급진단 규칙 (임계값은 JSON, signal 문구는 코드)
{"rules":[{"name":"보육시설 수급","demand_item":"유소년인구비율",
  "supply_kinds":["어린이집","유치원"],"demand_margin":1,
  "supply_low_max":3,"supply_high_min":10,"tag":"참고"}]}
```

---

## 7. 전체 로드맵

| 묶음 | Phase | 내용 | 상태 |
| --- | --- | --- | --- |
| **모드 B** (먼저) | P0 | 골격 + 스키마 (스텁) | ✅ 완료 |
| | P1 | 반경 시설 검색 (카카오) | ✅ 완료 |
| | P1.5 | 카카오 45건 상한 회피 (bbox 적응분할) | ✅ 완료 |
| | P1.5b | 공공데이터 경로당 등 공식시설 보강 | ✅ 완료 (2026-06-29, **VWorld 검색 API**로 해결 — data.go.kr 불필요. §8.5) |
| | P1.6 | 주소해석 견고화 (카카오+JUSO, 법정동코드) | ✅ 완료 |
| | P2 | VWorld 타일 게이트 | ✅ 완료 (VWorld 확정, Referer 불필요) |
| | P3 | 위성 PNG (핀·반경원·범례·축척·출처) | ✅ 완료 |
| **모드 A** | P4 | 용도별 목록 + 함의 룩업 (JSON) | ✅ 완료 (설정·로직, KOSIS는 P5) |
| | P5 | KOSIS 실조회 + 캐시 | ✅ 완료 (연령구조 5지표 + 1인가구비율·평균가구원수(census), 캐시 0콜. 잔여 §8.6) |
| | P6 | 한 문단 서술 + 폴백 | ✅ 완료 (Claude 1회, AI/규칙 폴백 둘 다 facts 보존) |
| **합치기** | P7 | 프론트 — A·B 탭 한 화면 | ✅ 완료 (React+Vite+Tailwind, dev 프록시 연결) |
| | P8 | Cloud Run 배포 | ✅ 완료 (arch-diagnose/서울, 공개URL 라이브, A·B·위성 검증) |
| **나중 확장** | P9 | 정렬·필터·여러 후보지 비교 | ✅ 완료 (/compare + 프론트 D탭, 후보지별 A·B·P11 나란히·컬럼정렬, 영등포vs강남 검증) |
| | P10 | '물어보기' 모드 (데이터 위에서만) | ✅ 완료 (/ask + 프론트 E탭, 그라운디드 답변·확인불가 하드블록·웹검색 opt-in 폴백 검증) |
| | P11 | 수급 진단 (A×B 교차) ★간판기능 | ✅ 완료 (/diagnose + supply_demand.json + 프론트 C탭, 영등포 실데이터 검증) |
| **데이터 확장** | P12 | matrix.json 멀티소스 구조 확장 (source_type 필드, KOSIS 외 소스 통합 설계) | 🟡 골격 완료·검증 후 막힘 (§8.7) |
| | P13 | 용도별 API 세트 매핑 (용도 선택 → 관련 소스만 호출, `API_MASTER_LIST.md` 기반) | 예정 |
| | P14 | 우선순위 소스 통합 ① 에어코리아·건축물대장·실거래가·문화재청 등 | ⚠️ 데이터셋 미승인 — §8.7 선결 |
| | P15 | 우선순위 소스 통합 ② 기상청·LURIS·HIRA·소상공인마당 등 | 예정 |
| | P16 | 용도 확장 (숙박·공공·산업·복합 등 신규 용도 추가) | 예정 |

### 진행 규칙

- **한 번에 한 Phase.** 완료 기준 통과 후 다음.
- P0 끝나면 스키마를 사람이 검토.
- "경로당" 등 비상업 시설 보강은 **VWorld 검색 API로 완료**(P1.5b, `services/vworld.py search_vworld` → `facilities.py`). data.go.kr 경로당은 백업.
- 새 데이터 소스 추가 시 `API_MASTER_LIST.md` 확인 → §2 차별점 체크리스트 통과 여부 먼저 확인.
- 막히면 추정으로 때우지 말고 멈춘다.

---

## 8. P11 — 수급 진단 (★간판 기능) 설계 메모 ✅ 완료

A(인구 수요) × B(시설 공급)를 교차해 "이 동네 무엇이 부족/과잉한가"를 근거와 함께 제시.
예: "반경 1km 어린이집 2개 + 유소년인구비율 전국평균 대비 높음 → 보육시설 수요 대비 공급 부족(참고)".
시장에 없는 조합. A·B 둘 다 있어야 가능 → 우리 구조에서만 나온다. 단 '부족/과잉'은 휴리스틱이므로 '참고' 태그 + 판단은 사람.

**구현 완료** — `/diagnose`, `services/diagnose.py`(`cross_rules` 순수로직은 P9·P10 공용), 규칙은 `app/data/supply_demand.json`(임계값), 프론트 C탭. 데이터계약은 §6 DiagnoseResult.

**정원 보강 (2026-06-29)** — 보육시설 수급에 어린이집 **정원**(시군구, 정보공개포털 cpmsapi021) 편입. 규칙 `capacity_source:"childcare"` → `_collect_capacity`가 `childcare.fetch_childcare`로 시군구 정원 조회 → `cross_rules(..., capacity_data=)` → `SupplySignal.capacity`. 반경 개수(판정)는 유지, 정원은 카카오에 없는 실데이터 공급량으로 note·필드 보강(단위 다름·참고, 절대 원칙 4). graceful — 정원 실패해도 진단 정상. compare는 capacity 미전달(하위호환).

---

## 8.5 P1.5b — 공공데이터 시설 보강 ✅ 완료 (VWorld 검색 API)

비상업 시설(경로당·마을회관 등)은 카카오 키워드에 누락될 수 있어 보강한다.
**해결 (2026-06-29)** — data.go.kr 경로당 표준데이터(code 30 미승인)를 기다리지 않고 **VWorld 검색 API**로 우회 완료.

- `services/vworld.py search_vworld(lat,lon,radius,kinds)` — `KIND_TO_VWORLD`(경로당·노인복지관·마을회관) category 필터로 오탐 제거. `facilities.py`가 카카오·OSM 뒤에 병합(`src="vworld"`), `source="kakao+...+vworld"`.
- 검증: 여의대로24 반경 2km 경로당 102건 집계(카카오 단독 ~0). **★수급진단 "노인복지시설 수급"이 실데이터로 정확**해짐(공급 121, 전엔 0 오판).
- data.go.kr 경로당(아래)은 **백업**. 아래 메모는 그 경로 참고용으로 보존.

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

KOSIS 키 동작 확인. **단, 지역코드 체계가 테이블마다 다름**(아래 ★ 주의).

### 확정 테이블 (실데이터 흐름)

- `DT_1B04005N` 행정구역(시군구)별/5세별 주민등록인구 (orgId 101, itmId T2, objL2=연령밴드 ALL).
  지역코드 = **행안부 시군구코드 = resolve 의 sgg_code** (영등포구 `11560`). C2코드 = 밴드시작나이+5
  (`5`=0-4세 … `70`=65-69세 … `105`=100+, `0`=계). 전국 = C1 `00`.
  - 5지표(한 테이블 1콜): 총인구수(direct) · 고령인구비율 · 유소년인구비율 ·
    생산가능인구비율(age_share) · 노년부양비(age_dependency).
- `DT_1JC1511` 가구원수별 가구(일반가구) - 시군구 (인구총조사, orgId 101, objL2=가구주연령, `000`=합계).
  ITM: `T100`=일반가구 · `T210`=가구원수1명(1인가구) · `T300`=평균가구원수.
  - 2지표: **1인가구비율**(method `ratio` = T210/T100×100) · **평균가구원수**(direct T300).
  - ★ 지역코드가 주민등록과 **다름** (영등포구 `11190` ≠ `11560`). 시도 2자리(`11`)만 공유 →
    테이블 지역목록(objL1=ALL)을 1회 호출(캐시)해 '시도접두+시군구명'으로 census 코드 역추출.
    matrix 항목에 `"region_scheme":"census"` 표시 → `stats.py`가 `kosis.resolve_census_region` 사용.

> ⚠️ §8.6 초기 가정("tblId만 채우면 코드 변경 불필요")은 census 계열에선 **틀림**. 주민등록과
> 다른 지역코드 + (비율의 경우) 새 계산 method 가 필요했다. 같은 지역코드·구조(주민등록)면 JSON만으로 OK.

### 미확정 지표 (matrix.json `method:"unconfirmed"` — 추정 않고 건너뜀)

- **인구밀도**: `DT_1B08024`(T7)는 **시도만** — 시군구 불가. 시군구는 총인구÷면적(면적표 결합) 필요.
- **사업체수·종사자수** [확정조사 완료 → 보류]: KOSIS에 시군구 단위 전체산업 사업체수가 깔끔히 없음.
  - orgId 101 전국사업체조사(`DT_1K52C01/C02`, 시도별 `INH_DT_1K52F01_NN`)는 **전부 시도 단위** — 시군구 차원 자체가 없음.
  - 시군구는 org 118 `DT_118N_SAUP75`(8개시)·`SAUP78`(9개도) **분리 테이블**뿐. 산업×규모×성별 4차원 → ALL 호출 시 40,000셀 초과(err 31), 또 다른 지역코드 체계.
  - ★ 더 근본: raw 사업체수를 전국 총량과 비교(현 national_avg 모델)는 무의미. **사업체밀도(개/㎢)·인구당 사업체수**로 재설계해야 의미 → 면적/인구 결합이 필요한 P11(수급진단)에서 함께 처리.
- 주택보급률·주간인구지수: orgId/tblId 미확정. 데이터 응답(itmId=ALL,objL=ALL)에서 코드 역추출.

### 캐시

- `services/cache.py` Cache 인터페이스(get/set) + FileCache(out/kosis_cache). GCS 교체 가능.
  키 = (orgId,tblId,지역,연도,objL2,itmId). 동일요청 재호출 0콜 확인.

---

## 8.7 API 연결 검증 현황 (2026-06-26)

`.env` 17개 키를 전부 **실제 엔드포인트로 실호출**해 분류함. 재현 스크립트는 `scripts/verify_apis.py`(+ 정밀 2차 `verify_apis2.py`), 결과 JSON은 `out/verify_apis_result.json`, **상세 표·근거는 [docs/API_VERIFICATION_2026-06-26.md](docs/API_VERIFICATION_2026-06-26.md)**. (키 값은 어디에도 출력 안 함.)

> 한 줄 결론: **기존 기능(모드 A·B·diagnose·compare·ask)은 정상(pytest 65 통과). 새로 키 붙인 data.go.kr 확장이 "데이터셋 미승인"으로 전부 막혀 실데이터가 0이다.**

### ✅ 작동 확인 (9키)

KAKAO · VWORLD · KOSIS · JUSO · ANTHROPIC(claude-opus-4-8) · **KMA**(apihub, `authKey=`) · **RONE**(SttsApiTblData, `KEY=`) · **SEOUL**(INFO-000) · **NEIS**(schoolInfo) · **KOPIS**(`prfplc`). + OSM(무료, 이미 `facilities.py` 연결).

### 🟡 DATA_GO_KR — 키는 유효, 데이터셋별 승인이 갈림 (★중요)

- **판정 근거**: data.go.kr 는 *미승인 데이터셋*을 게이트웨이가 **403 Forbidden / 500 Unexpected**(평문)로 막음. *키가 틀리면* 표준 XML `resultCode=30`. 우리는 30이 아니라 403/500을 받았고 **동일 키로 7종이 정상** → 키 OK, 데이터셋 승인이 갈린 것.
- **작동**: 상가(상권)정보(B553077) · 응급의료기관(B552657) · HIRA병원(B551182) · 토지매매 · 연립다세대매매 · 아파트전월세 · 오피스텔전월세. **+ (2026-06-29 추가 승인 전파)** 아파트**매매** #33 · 건축HUB 건축물대장(`BldRgstHubService`) · 에어코리아 **측정값**(`ArpltnInforInqireSvc`, 단 측정소검색 `MsrstnInfoInqireSvc`는 여전히 403).
- **미승인(=코드는 있는데 실데이터 0)**: 표준지공시지가 #35(500, **VWorld로 우회 완료 — 불필요**) · 구버전 건축물대장 `BldRgstService_v2` #48(500, **건축HUB로 대체**) · 공장창고매매(403) · 경로당/마을회관(code30, **VWorld 검색으로 우회 완료**) · 어린이집(code30) · 문화기반시설총람 B553457(500, 신청완료·대기).
- **영향 (대부분 해소됨)**:
  - ~~`services/airkorea.py`~~ → ✅ 해소: `getCtprvnRltmMesureDnsty`(승인됨)로 재배선, `/analyze` 대기질 4항목 실데이터(§9.1-3).
  - ~~`services/molit.py` + `/site`~~ → ✅ 해소: 공시지가=VWorld, 실거래 4종·건축물대장=승인 데이터(§9.1-1). `/site` §5 표 등재+테스트 완료.
  - 전부 graceful 처리라 앱은 안 죽음(절대 원칙 3 준수).

### 🔴 키/계정 미활성·인증실패 (사용자 액션 필요)

- **TMAP #103**: 쿼리·헤더 둘 다 `403 INVALID_API_KEY` → SK OpenAPI 콘솔에서 앱 활성화/해당 API 구독 확인.
- **LIBRARY #122**: "API 활성화 상태가 아닙니다" → data4library 계정 OpenAPI 활성화 승인.
- **CULTURE #134**: data.go.kr B553457 미승인(500) + kcisa(`API_CCA_###`) 401. ※ `API_CCA` 계열은 공연·전시 *콘텐츠*이지 시설총람 아님 → 진짜 #134는 **data.go.kr B553457(DATA_GO_KR키) 활용신청** 경로. 둘 중 하나 확정 필요.

### ⚫ SBIZ365 #29·#30 — REST API 자체 없음 (재분류)

소상공인365는 대시보드+파일(CSV/PDF)만. `SBIZ365_KEY`=포털용(fetch 불가). 매출/폐업/창업·빈상가는 **fileData 주기적 적재**가 유일 경로. 상권 실API는 이미 쓰는 data.go.kr B553077(점포분포)뿐 → §2 차별점 체크리스트 1번 불충족.

### ⬜ EUM(EUM_ID/EUM_KEY) — 범위 밖

규제정보 = arch-law-diagnose 담당(INTEGRATION.md §2, DEFERRED D6). 의도적으로 SKIP — 미검증 보류.

### 발견한 코드 버그

- ~~`app/services/airkorea.py`: getMsrstnList 서비스경로 버그~~ → ✅ **수정완료** (2026-06-29, §9.1-3). 측정소검색(`MsrstnInfoInqireSvc`)이 미승인(403)이라 아예 의존 제거하고 `getCtprvnRltmMesureDnsty`(시도 전체, 승인됨)+이름매칭으로 재배선.

### 다음 액션 (두 갈래)

- **(사용자) 포털**: data.go.kr 활용신청 — 에어코리아 B552584 · 표준지공시지가 · 건축물대장(BldRgstService_v2) · 아파트매매(RTMSDataSvcAptTradeDev) · 경로당 · 어린이집. TMAP 앱 활성화. LIBRARY 활성화. #134 경로 택1.
- **(코드)**: ① `molit.py`/`/site` 를 *승인된* 토지·전월세·연립다세대 실거래로 재배선(지금 실데이터 나오게) ② `airkorea.py` 서비스경로 수정 ③ 검증된 신규 5키(KMA·RONE·SEOUL·NEIS·KOPIS) 서비스 골격 추가(P14) ④ `verify_apis.py` 를 주기 점검 자산으로 유지(키 만료·승인전파 감지).
- 새 소스 배선 시 **반드시 `docs/API_VERIFICATION` 에서 작동 확인된 엔드포인트만** 사용.

---

## 9. 다음에 할 일 (NEXT) — 2026-06-26 기준

> 검증(§8.7) 직후 정리한 실행 목록. 한 번에 한 덩어리, 끝나면 체크하고 상태 갱신.
> 코드 작업은 **승인 여부와 무관하게 지금 가능한 것부터**. 사용자 포털 액션은 병렬로 진행.

### 9.1 다음에 할 일 (코드 — 지금 가능, 우선순위 순)

1. **`/site`·`molit.py` 재배선** — 🟡 진행중.
   - ✅ **공시지가: VWorld 우회 완료** (2026-06-29). `app/services/vworld.py fetch_land_price` = 연속지적도 `LP_PA_CBND_BUBUN`의 `jiga`(개별공시지가, 필지별). data.go.kr 표준지/개별 미승인(403/500) 불필요. `/site` 라이브 테스트 추가(`tests/test_site_live.py`), §5 표 등재 완료. 여의대로24→여의도동28-1 29,793,000원/㎡(2025) 실데이터 검증. 호출 주의: `domain` 파라미터=등록도메인(VWORLD_DOMAIN, 기본 Cloud Run 호스트) 필수.
   - ✅ **실거래 재배선 완료** (2026-06-29). `molit.fetch_trades` = 종류별 레지스트리(`_RTMS`)로 통합. `/site`가 `DEFAULT_TRADE_KINDS`(토지매매·아파트매매·연립다세대매매·아파트전월세) 4종 각 5건 = 실데이터 20건 반환. **아파트매매(#33)는 사용자 재신청 후 승인 전파됨**(403→000). 스키마 `AptTrade`→`Transaction`(매매·전월세 공통, 토지는 `note`에 용도지역). 버그수정: RTMS는 `resultCode=000`(0 세 개)인데 `_check_xml_result`가 `00`만 인정 → `000` 추가. 라이브 테스트 `test_molit_land_trade`.
   - ✅ **건축물대장 완료** (2026-06-29). 사용자가 **건축HUB**(`BldRgstHubService`) 활용신청 → 작동(구버전 `BldRgstService_v2`는 여전히 500). `molit.fetch_building(pnu)` = VWorld 공시지가의 `pnu`(필지)로 정확 조회: 표제부(`getBrTitleInfo`) 대표건물(연면적 최대) + 총괄표제부(`getBrRecapTitleInfo`) 단지 전체 건폐율·용적률 보정. `_parse_pnu`로 PNU 19자리→sigunguCd/bjdongCd/platGb/bun/ji. 검증: 여의대로24=에프케이아이타워 지상50/지하6, 건폐52.75% 용적940.36%. 라이브 테스트 2건.
   - ⬜ `/site` 1번 묶음 완료. `verify_apis.py`는 구버전 대장 엔드포인트를 봄 → 건축HUB로 갱신 권장(§9.3).
2. ~~경로당/비상업시설 보강~~ → ✅ **완료** (2026-06-29). VWorld 검색 API로 모드 B 보강 (P1.5b·§8.5). `services/vworld.py search_vworld` + `facilities.py` 병합. 수급진단 노인복지 항목 정확화.
3. ~~`airkorea.py` 서비스경로 버그 수정~~ → ✅ **완료** (2026-06-29). 실측 결과: **측정값 서비스(`ArpltnInforInqireSvc`)는 승인됨(200), 측정소검색(`MsrstnInfoInqireSvc/getMsrstnList`)만 미승인(403)**. → 미승인 검색 의존을 버리고 `getCtprvnRltmMesureDnsty`(시도 전체 측정값, 승인됨)에서 시군구명 매칭(`_pick_station`)으로 측정소 선택. 매칭 없으면 임의 대체 없이 건너뜀(절대 원칙 3). 좌표기반 최근접은 측정소검색 승인 후 개선. **`/analyze` 대기질 4항목(PM2.5·PM10·O3·NO2) 실데이터로 채워짐** — "광고는 하는데 빈값" 해소. 라이브 테스트 `test_airkorea_live.py`.
4. ~~검증된 신규 5키 서비스 골격 추가 (P14)~~ → ✅ **완료** (2026-06-29). 5개 서비스 모듈 + 라이브 테스트 8건. 각 graceful·캐시·검증 엔드포인트만:
   - `services/kma.py` `fetch_weather(lat,lon)` — 좌표→기상청격자(`dfs_xy` LCC) → 단기예보 기온·강수확률·하늘(apihub, timeout 35s). ✅ 작동
   - `services/rone.py` `fetch_price_index(region,statbl)` — 부동산원 R-ONE 매매가격지수, 지역명 매칭·최근시점(START/END_WRTTIME로 최신 확보). ✅ 작동
   - `services/neis.py` `fetch_schools(sido,sigungu,level)` — 시도교육청별 학교, 도로명주소로 시군구 필터·종류별 집계. ✅ 작동(영등포 47교)
   - `services/seoul.py` `fetch_living_population(행정동코드)` — 서울 생활인구(최신가용일 자동탐지+동·시간대 필터, 서울전용, ~5일지연). ✅ 작동
   - `services/kopis.py` `fetch_venues(signgucode)` — 공연시설. ⚠️ **키 현재 `returncode 02`(미등록)** — 골격 완성, graceful, 키 재등록 시 작동.
   - ✅ **엔드포인트 배선 완료** (2026-06-29): 5키 전부 `POST /seed` 의 context 에 배선(아래 7번). ✅ **SEOUL 행정동코드 자동화** (2026-06-29): 좌표→`kakao.coord_to_hcode`(coord2regioncode H코드)→`[:8]`=서울 ADSTRD_CODE_SE. `seoul.fetch_living_population(lat,lon)` 자동 해석. ⬜ 잔여: KOPIS 시군구코드 매핑·matrix `source_type` 통합(모드A 편입은 선택).
5. ~~SBIZ365 #29·#30 재분류~~ → ✅ **완료** (2026-06-29). 판정: SBIZ365는 REST API 없음(`SBIZ365_KEY`=포털용, fetch 불가). **결정**:
   - 점포 '분포'(업종별 점포수)는 작동하는 실API **B553077 상가(상권)정보**를 `services/sangwon.py`로 정식 승격(데모→서비스). `fetch_store_district(lat,lon,radius)` = 반경 내 점포수+업종 대분류 집계. 여의도 500m 2,275개 검증. 라이브 테스트 1건. §2 차별점 통과(실API·코드계산·출처).
   - 매출/폐업/창업률·빈상가(#29b·#30)는 fileData CSV 적재만 가능 → **현재 제외**(§2 실시간 API 우선·bus-factor). 필요시 후속 CSV 적재 설계. API_MASTER_LIST.md 갱신.
   - ✅ 엔드포인트 배선: `sangwon.py` → `POST /seed` context.stores (7번). ⬜ 잔여: 수급진단 업종분석 편입(선택).
6. ~~INTEGRATION.md P12 연결 준비~~ → ✅ **완료** (2026-06-29). 3종 준비물:
   - `services/http_retry.py` `request_with_retry` — 5xx·네트워크만 재시도(지수백오프), 4xx 즉시. 단위테스트 5건(MockTransport). ✅ **기존 외부호출 전반 적용 완료** (2026-06-29): kakao·resolve·juso·kosis·vworld·molit·airkorea·sangwon·rone·neis·seoul·kopis·kma 의 GET 22곳. tiles(타일별 회색채움 설계)·osm(Overpass rate-limit)은 의도적 제외.
   - `schemas/project_seed.py` `Site`/`ProjectSeed` — 세 앱 공유 계약(INTEGRATION §4). site=공유 식별자(좌표·bcode·sgg·pnu), context=터읽기, law/knowledge=형제앱(느슨 dict, 경계).
   - `services/site_seed.py` `build_site`/`build_project_seed` — 주소 해석 단일진입점(resolve 1곳 + VWorld pnu 보강). 라이브테스트 3건.
7. ✅ **신규 서비스 7종 엔드포인트 배선 완료** (2026-06-29). `POST /seed`(`routers/seed.py`) = 보드 합본 진입점. `build_site`(site_seed)로 공유 site + `context`에 6개 데이터 서비스 best-effort 배선: stores(sangwon)·schools(neis)·real_estate_index(rone)·weather(kma, timeout 12s)·living_population(seoul, adstrd_code 지정 시)·venues(kopis). 각 graceful(None+notes). 출력=`ProjectSeed`(law·knowledge는 형제앱 자리). §5 표 등재, 라이브 테스트 2건. 검증: 여의대로24 1km → 상권5922·학교47·지수89.9·날씨29℃·생활인구191469·공연None(키대기). 버그수정: resolve sido가 카카오 축약형("서울")이라 NEIS `_OFC_CODE`에 축약형 추가.
   - ✅ http_retry 전반 적용·SEOUL 행정동코드 자동화·KOPIS 시군구 매핑·`verify_apis.py` 갱신 완료(2026-06-29). KOPIS는 키 미등록(02)으로 signgucode 체계 검증 불가 → 추정 않고 응답 `gugunnm` **이름 필터**(`fetch_venues(sido,sigungu)`). `verify_apis.py`: 건축HUB 표제부·VWorld 개별공시지가 프로브 추가, 아파트매매 `resultCode=000` 정상인식, KOPIS 02 정확분류. 실행결과 WORKS=15. ⬜ 잔여: 죽은 `molit.fetch_land_price` 정리, 프론트 노출.

### 9.2 확인할 것 (사용자 포털 액션 — 풀려야 코드가 의미 생김)

- [ ] **data.go.kr 활용신청**: 에어코리아 `B552584`(신청완료·대기) · 건축물대장 `BldRgstService_v2` · 아파트매매 `RTMSDataSvcAptTradeDev`(신청완료·대기) · 문화기반시설총람 `B553457`(신청완료). → 승인 후 `scripts/verify_apis.py` 재실행으로 전파 확인(403/500→00).
  - ~~표준지공시지가~~ → **불필요**: VWorld 개별공시지가로 우회 완료(§9.1-1).
  - 경로당(15114136) → **VWorld 검색 API로 우회 완료**(§8.5). 어린이집 → ✅ **정보공개포털 cpmsapi021 연결 완료**(2026-06-29, `CHILDCARE_INFO_KEY`, `services/childcare.py`→`/seed`. 영등포 50개·정원2785 검증). data.go.kr 경로는 불필요.
  - 문화기반시설총람 `B553457` → ✅ **연결 완료**(2026-06-29, `services/culture.py`→`/seed` context.culture). `DATA_GO_KR_API_KEY`+`pblshYr`(발간연도 자동탐지, 최신2024)+`sggCd`, 10개 시설유형 operation(박물관·미술관·문예회관·국립/공공도서관·생활문화센터·지방문화원·문화의집·지역문화재단·문학관). 종로73·강남31·부산중구7 등 전국 검증. ⚠️ kcisa `CULTURE_KEY`는 401 — data.go.kr 경로가 정답.
  - **KOPIS** → ✅ 키 갱신 후 인증 통과(이전 02). **어린이집 상세** cpmsapi030(`CHILDCARE_DETAIL_KEY`, 위경도·CCTV·연령별정원)은 arcode 체계 별도 — 필요 시 추가.
- [ ] **TMAP #103**: SK OpenAPI 콘솔에서 앱 활성화 + 사용할 API 구독 (현재 `403 INVALID_API_KEY`).
- [ ] **LIBRARY #122**: data4library 계정 OpenAPI 활성화 승인 (현재 "API 미활성").
- [ ] **CULTURE #134 경로 택1**: data.go.kr `B553457` 활용신청 **또는** kcisa 구독 데이터셋의 정확한 `API_CCA` 번호 확인.
- [ ] **JUSO 운영키 (DEFERRED D2)**: 배포 전 dev키→운영키 교체.
- [ ] **KOPIS 키 재등록**: 검증(6/26)땐 작동했으나 6/29 `returncode 02 (SERVICE KEY NOT REGISTERED)`로 거부. `kopis.py` 골격은 완성 — 키만 풀리면 작동.
- [ ] **EUM 진행 여부 결정 (DEFERRED D6)**: 규제=arch-law-diagnose 담당 — 가져올지/말지 제품 결정.

### 9.3 하면 좋은 것 (개선·기술부채)

- **`verify_apis.py` 주기 점검 자산화** — CI/cron 으로 키 만료·승인 전파 자동 감지. ✅ 2026-06-29 현황 반영(건축HUB·VWorld 공시지가 프로브 추가, 아파트매매 000 인식, KOPIS 02 분류). 실행 WORKS=15. ⚠️ VWorld 개발키 **2026-12-26 만료**(INTEGRATION.md §5) 추적.
- **테스트 보강** — `/site` 무테스트. → ✅ 해소(test_site_live·test_seed_live·신규서비스 live 추가).
- **KOSIS 미확정 지표 확정 (DEFERRED D4, §8.6)** — 인구밀도·사업체수·주택보급률 등. 면적/인구 결합은 P11 수급진단에서 함께.
- **matrix.json / implications.json 건축가 검수 (DEFERRED D5)** — 항목·우선순위·함의 규칙 실설계 관점 보강(코드 수정 없이 JSON만).
- **인프라 부채** — StarletteDeprecation httpx 경고(D7), GCS 캐시+TTL(D8), 합성 PNG 다중인스턴스(D10).
