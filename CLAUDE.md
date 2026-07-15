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
- **종합 읽기 (S/T 시리즈, `/board`·I탭 ★)**: 흩어진 출력을 하나로 합성 + 해석 레이어 — 데이터 근접도(S1)·교차규칙(S2)·**동네 유형(T1.5)·설계 드라이버(T2)·프로그램 함의 POR(T3)**·사실/AI의견 벽 분리 종합(S4). 공유·인쇄 보드 내보내기(T4)·MCP·형제앱(competition) 연동. 전부 LLM 0(S4 표현만)·새 숫자 0. 상세 §8.11·§8.12.

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
5. **판단은 분리·라벨하되 최종 결정은 사람** — 사실(검증됨)과 AI 의견을 **벽으로 분리·라벨**해 제시한다. AI 판단(S4 ②)은 ⓐ근거 fact 인용 ⓑ가정 명시 ⓒ새 숫자 금지 3조건 하에서만. 좋다/나쁘다·사업성 금액·수익률 단정은 여전히 금지 — 최종 결정은 사람. *(S4 이전 문구: "판단은 사람". 2026-07-09 의도된 진화 §8.11.)*
6. **모델은 Claude 하나** — 다벤더·교차검증 금지 (정답이 정해진 데이터엔 잡음만 는다). Claude 계열 내 티어 분리는 허용: S4는 ①서술=Sonnet·②판단=Opus 2콜이지만 여전히 Claude 한 벤더.
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
- 배포: GCP Cloud Run + Secret Manager(키). 캐시는 **파일캐시**(`services/cache.py FileCache`, `OUT_DIR=/tmp/out` — Cloud Run 임시 FS라 인스턴스별·비영속). GCS 캐시(`GCSCache`)는 코드에 있으나 **미연결**(`GCS_CACHE_BUCKET` 미설정 시 파일캐시) — §9.3 D8 부채.
- **MCP 아님** — 순수 FastAPI HTTP 엔드포인트. (파이프라인 연결은 나중에 project_seed JSON)
- 로컬: Windows, 프로젝트 `D:\APPS\arch-site-context`. **venv는 풀경로로 생성, Microsoft Store python 금지.**
- 키(.env, 절대 커밋 금지): `KAKAO_KEY`, `JUSO_API_KEY`(주소 폴백·현재 dev키), `VWORLD_KEY`, `KOSIS_KEY`, `ANTHROPIC_API_KEY`, `DATA_GO_KR_API_KEY`(에어코리아·실거래·건축물대장·문화시설총람 등 다수), `KMA_KEY`(기상청 apihub), `RONE_KEY`(부동산원 R-ONE), `NEIS_KEY`(학교), `TMAP_KEY`(SK 보행자 등시선), `SEOUL_API_KEY`(생활인구, 서울전용), `KOPIS_KEY`(공연시설), `CHILDCARE_INFO_KEY`(cpmsapi021, 어린이집 개수·정원), `CHILDCARE_DETAIL_KEY`(cpmsapi030, 위경도·형태·상세 — 운영계정 전환 대기, §8.13), `SGIS_KEY`/`SGIS_SECRET`(통계청 SGIS 2키, 반경 집계구 인구 — D2), `SBIZ365_KEY`(REST API 없음·포털용), `LIBRARY_KEY`(미활성), `EUM_ID`/`EUM_KEY`(범위 외·보류), (선택)`VWORLD_REFERER`
- 전체 소스 목록·키 상태·우선순위는 **`API_MASTER_LIST.md`** 참조 (약 161개 소스, ✅기존키/🔑새키/💰유료/⚠️제한 구분).

### 외부 API

- **카카오 로컬**: 주소→좌표, 키워드 반경검색 (모드 B)
- **JUSO(행안부 도로명주소)**: 카카오 주소검색 0건 시 정규화·법정동코드 폴백 (P1.6)
- **VWorld**: 항공영상 타일 `https://api.vworld.kr/req/wmts/1.0.0/{KEY}/Satellite/{z}/{y}/{x}.jpeg` (jpeg). 키가 도메인 잠금일 수 있음 → 안 되면 카카오 스카이뷰로 폴백.
- **KOSIS OpenAPI**: 지역 통계 (모드 A). HTTPS 필수, 분당 호출 제한 있음 → 캐시 우선.
- **Claude API**: ① 한 문단 서술 1회 (모드 A P6) ② 물어보기 그라운디드 답변 (P10) ③ 물어보기 웹검색 폴백 — Claude 내장 `web_search` 서버툴 (P10, opt-in) ④ **종합 산출(S4)** — ①사실 종합=`claude-sonnet-5`·②AI 판단=`claude-opus-4-8`, 벽 분리·라벨 (§8.11). 모두 Claude 계열 — 원칙 6.

---

## 4.1 새 로컬 환경 세팅 (다른 PC에서 개발 시작할 때)

### 사전 설치 확인

- **Python 3.11** — 공식 [python.org](https://python.org) 설치 (Microsoft Store 버전 금지)
- **Node.js** LTS
- **Git**

### 세팅 순서

```bash
# 1. 코드 받기
git clone https://github.com/DaDaDiRaRa/arch-site-context.git
cd arch-site-context

# 2. 백엔드 환경
python -m venv D:\APPS\arch-site-context\.venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. 프론트엔드 환경
cd frontend
npm install
cd ..
```

**`.env` 파일은 수동으로 복사** (Git에 포함되지 않음 — 기존 PC에서 가져오기).  
그 외 `out/`(캐시)·`node_modules/`·`.venv/` 등은 위 명령어로 자동 생성되므로 복사 불필요.

### 실행 확인

```bash
# 터미널 1 — 백엔드
.venv\Scripts\activate
uvicorn app.main:app --reload

# 터미널 2 — 프론트엔드
cd frontend
npm run dev
```

### 이후 개발 루틴 (PC 간 전환)

```bash
git pull        # 작업 시작 전 항상
# ... 작업 ...
git add <파일>
git commit -m "..."
git push        # 작업 후 GitHub에 올리기
```

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
| POST | `/site` | P14 | 대지 기본정보 (개별공시지가=VWorld·실거래·건축물대장 + **재해위험**=SGIS 홍수·산사태 영향범위, §8.10). 공시지가는 data.go.kr 미승인 → VWorld `LP_PA_CBND_BUBUN` 우회 |
| POST | `/seed` | P14 | 보드 합본 진입점 — 공유 site(좌표·pnu) + context(상권·학교·어린이집·문화시설·부동산지수·날씨·생활인구·공연시설). `schemas/project_seed.ProjectSeed`. law·knowledge는 형제앱 자리(INTEGRATION). 8블록 ThreadPoolExecutor 병렬 |
| POST | `/readout` | - | 공동주택 대지 readout — 인구·가구(matrix) + 산업·주거·복지(KOSIS 다차원 census 크랙) + 파생 + 유형 프리셋(재건축/재개발/민간/주상복합). `services/{readout,census_multidim}.py`. 전국 작동 |
| POST | `/board` | S3·S4·T | 대지 종합 읽기 — analyze·diagnose·site·seed **병렬 오케스트레이션**(새 데이터 0) + S1 근접도 + **S2 교차시사점** + **T2 설계 드라이버**(design_drivers, 증거강도 랭킹) + **T5 방법론 부록**(methodology, 출처·산정식·한계 자동 각인) + 도메인 coverage. `synthesize=true`면 **S4 종합 산출**(①Sonnet·②Opus 벽분리). **`brief=true`면 압축 투영(board_brief/1.0)** — 제안서·MCP·형제앱 주입용(원시 seed context 제외). **`model=`(선택)이면 arch-site-model 물리 3D 요약 병합**(assembler 가 넘김·터읽기는 호출 안 함, 물리+인문=완전한 보드). `schema_version:"board/1.0"`. 종합점수 없음. 프론트 I탭 |
| POST | `/board/view` | T4 | 대지분석 보드 HTML 렌더 — /board 빌드 → 자체완결 한 장(지도앵커·**물리모델 축측매싱**·드라이버·S4·지수·부록·출처) → `out/boards/*.html` 저장, `/files/...` **공유 URL** 반환. 인쇄→PDF. `services/board_view.py` |
| POST | `/context-pack` | C1·C2·C6 | **심의 현황팩** — 주소+신축세대(다획지 list) → 조사범위 걸침 인구·세대(C1 `survey.py`) + 구 영유아·세대(KOSIS/jumin) + 시설현황(`survey_facilities.py`) + 주민공동시설 총량제 부족/충족 판정(C2 `quota.py`, `community_quota.json` 세대규모 tier). `services/deliberation.py assess_quota`→`QuotaAssessment`. 프론트 J탭 |
| POST | `/context-pack/pptx` | C4·C5 | 심의 현황팩 **A3 편집가능 PPTX** — 걸침표·시설현황표·편집가능 위치도(위성+네이티브 반경원·번호핀)·총량제 판정박스 → `out/packs/*.pptx` 저장·`/files/...` 공유 URL. `services/deliberation_pptx.py` |
| POST | `/surroundings` | C7 | **주변현황도**(심의 슬라이드 4~6) — 반경 내 교통·교육·여가·주거·관공서 카카오 수집(카테고리 코드 정제·노이즈 필터) + 서술문 룰조립(LLM 0). `services/surroundings.py`. 프론트 K탭 |
| POST | `/surroundings/pptx` | C7 | 주변현황도 A3 PPTX — 위성 반경현황도(카테고리 색점)+카테고리표+서술문 → `/files/packs/*.pptx`. `services/surroundings_pptx.py` |
| GET | `/health` | - | 헬스체크 |
| GET | `/api` · `POST /basemap` | - | 진입 안내(`/api`) · 위성 basemap 합성(`/basemap`, `routers/facilities.py`) |

> **프론트 탭 지도** (`frontend/src/App.jsx`): I 종합읽기 · A 지역통계 · B 주변시설 · C 수급진단 · D 후보지비교 · E 물어보기 · F 대지정보(/site) · G 종합(/seed) · H 공동주택 readout · J 심의 현황팩 · K 주변현황도 · **L 대지분석 덱**. **TabL** 은 터읽기 엔드포인트가 아니라 형제앱 **deck-builder**(`D:\APPS\deck-builder`, 대지분석 덱 자동생성)에 연결되는 프론트 전용 탭 — 현재 미추적(WIP).

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
// 현재 6개 규칙: 보육시설·노인복지시설·1인가구 생활시설·의료시설·초등학교·문화시설
// capacity_source:"childcare" → _collect_capacity가 cpmsapi021 정원 조회 후 SupplySignal.capacity 보강 (반경 개수와 단위 다름·참고)
{"rules":[
  {"name":"보육시설 수급","demand_item":"유소년인구비율",
   "supply_kinds":["어린이집","유치원"],"demand_margin":1,
   "supply_low_max":3,"supply_high_min":10,"capacity_source":"childcare","tag":"참고"},
  {"name":"의료시설 수급","demand_item":"고령인구비율",
   "supply_kinds":["병원","의원","약국"],"demand_margin":2,
   "supply_low_max":10,"supply_high_min":30,"tag":"참고"},
  {"name":"초등학교 수급","demand_item":"유소년인구비율",
   "supply_kinds":["초등학교"],"demand_margin":1,
   "supply_low_max":0,"supply_high_min":3,"tag":"참고"}
]}
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
| | P8 | Cloud Run 배포 | ✅ 완료 (**서비스명 `arch-site-context`** / 프로젝트 `arch-diagnose` / 리전 `asia-northeast3`, 라이브 `https://arch-site-context-dqj4exlefq-du.a.run.app`, 시크릿 15개·메모리 1Gi. 2026-07-15 전 기능 재배포 rev00048 — S/T 시리즈·MCP·심의팩 라이브화) |
| **나중 확장** | P9 | 정렬·필터·여러 후보지 비교 | ✅ 완료 (/compare + 프론트 D탭, 후보지별 A·B·P11 나란히·컬럼정렬, 영등포vs강남 검증) |
| | P10 | '물어보기' 모드 (데이터 위에서만) | ✅ 완료 (/ask + 프론트 E탭, 그라운디드 답변·확인불가 하드블록·웹검색 opt-in 폴백 검증) |
| | P11 | 수급 진단 (A×B 교차) ★간판기능 | ✅ 완료 (/diagnose + supply_demand.json + 프론트 C탭, 영등포 실데이터 검증) |
| **데이터 확장** | P12 | matrix.json 멀티소스 구조 확장 (source_type 필드, KOSIS 외 소스 통합 설계) | 🟡 골격 완료·검증 후 막힘 (§8.7) |
| | P13 | 용도별 API 세트 매핑 (용도 선택 → 관련 소스만 호출, `API_MASTER_LIST.md` 기반) | 예정 |
| | P14 | 우선순위 소스 통합 ① /site(공시지가·실거래·건축물대장) + /seed(상권·학교·부동산지수·날씨·생활인구·공연·어린이집·문화시설) + 수급진단 5규칙 | ✅ 완료 (2026-06-29) |
| | P15 | 우선순위 소스 통합 ② 기상청·LURIS·HIRA·소상공인마당 등 | 예정 |
| | P16 | 용도 확장 (숙박·공공·산업·복합 등 신규 용도 추가) | 예정 |
| **해상도 확장** | D1 | 읍면동 해상도 옵션 (모드A·수급진단 demand를 동 단위로) | ✅ 완료 (2026-06-30, §8.8) |
| | D2 | 진짜 반경 인구 (통계청 SGIS 집계구) — 수급진단 demand를 반경 실인구로 | ✅ 완료 (2026-06-30, §8.9) |
| **종합·해석** | S1 | 데이터 근접도 레이어 (모든 수치에 대지근접도 등급: 대지>반경>읍면동>시군구>proxy) | ✅ 완료 (2026-07-09, §8.11) |
| | S2 | 교차규칙 엔진 (도메인 횡단 '참고' 시사점 + 근거, JSON·LLM 0) | ✅ 완료 (2026-07-09, §8.11) |
| | S3 | `/board` 통합 진입점 (전 도메인 + S2 + 결측목록, 기존 서비스 재사용·병렬) | ✅ 완료 (2026-07-09, §8.11) |
| | S4 | 종합 산출 = 해석(Sonnet, 그라운디드) + 판단(Opus, 분리·라벨) 두 블록 | ✅ 완료 (2026-07-09, §8.11) |
| **신뢰·활용** (T, §8.12) | T1 | 정규화 지수(전국=100)+근거 드릴다운 (Esri US=100·Local Logic 드릴다운) | ✅ 완료 (2026-07-09) |
| | T1.5 | 대지 아키타입(동네 유형) — 규칙 룩업·한글 유형명·2계층 (Esri Tapestry, K-means 아님) | ✅ 완료 (2026-07-09) |
| | T2 | 설계 드라이버 합성 (분석→설계 다리, 지배 드라이버 2~3개) ★blue ocean | ✅ 완료 (2026-07-09) |
| | T3 | 프로그램 함의(POR seeds) — 드라이버→공간·프로그램 권고 (program_rules.json) ★blue ocean | ✅ 완료 (2026-07-09) |
| | T4 | 대지분석 보드 + 딜리버리 (공유링크·PDF·API, 지도앵커·패널그리드) | ✅ 완료 (2026-07-09) |
| | T5 | 방법론·데이터 부록 (공공 공모·감사 대비) | ✅ 완료 (2026-07-09, §8.12) |
| **심의 현황팩** (§8.13) | C1 | 조사범위 걸침 행정동 합산 (걸침비율+인구·세대+생활권 플래그) | ✅ 앱 배선 (`survey.py`, 2026-07-14) |
| | jumin | 행안부 rdoa 행정동별 인구+세대 서비스 (무키·전국) | ✅ 앱 배선·테스트 (2026-07-12) |
| | C2 | 총량제 산정식 (community_quota.json, 세대규모 5-tier·조례검증) | ✅ 앱 배선 (`quota.py`, 2026-07-14) |
| | C3 | 시설 상세화 (어린이집 형태=cpmsapi030 운영계정 대기) | 🟡 형태 대기 |
| | C4·C5 | 조사범위 위치도(편집가능 도형)·A3 편집가능 PPTX | ✅ 앱 배선 (`deliberation_pptx.py`, 2026-07-14) |
| | C6 | `/context-pack` 오케스트레이션 (C1+구통계+시설현황+C2) + 프론트 J탭 | ✅ 완료 (`deliberation.py`, 2026-07-14) |
| | C7 | 주변현황도 (슬라이드 4~6): 반경 현황도+카테고리표+서술문 + 프론트 K탭 | ✅ 완료 (`surroundings.py`, 2026-07-14) |

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

**규칙 확장 (2026-06-29~30)** — supply_demand.json에 **의료시설 수급**(고령인구비율×병원·의원·약국, low_max=10, high_min=30)·**초등학교 수급**(유소년인구비율×초등학교, low_max=0, high_min=3)·**문화시설 수급**(생산가능인구비율×도서관·미술관·박물관·문화센터·공연장·영화관, low_max=2, high_min=12) 추가 → 총 6개 규칙. 코드 변경 없음, JSON만으로 자동 반영(절대 원칙 7). 문화시설 수요 proxy는 생산가능인구비율(문화 관람·참여 핵심연령대) — 단일 proxy라 약함·도심 동반상승 한계 note 명시.

**★공급 판정 반경 1인당 정규화 (2026-06-30)** — 반경 모드(`resolution='반경'`)에서 공급 판정을 "개수 임계값 휴리스틱"에서 **"반경 실인구 1만명당 시설수 vs 전국 1만명당"(primary)**으로 격상. 분자(반경 시설수)·분모(반경 실인구=SGIS 집계구 합산, D2)·기준(전국 1인당, JSON `national_density_per_10k`) 전부 실측·1인당. `cross_rules(..., radius_pop=)` → `_supply_level_density`(density_low_pct/high_pct, 기본 60/150%)가 primary, `SupplySignal.density_basis='반경'`. 구/동 모드는 radius_pop 없음 → 기존 개수 임계값 유지(하위호환). **효과(여의도 1km 실측)**: 시군구 분모(37만)에선 밀도가 무의미(전부 8%·4%…→개수로 전부 '많음')했는데, 반경 분모(29,281)로 의미화 — 노인복지 6.83/만명=전국 53%→**적음**(경로당 20개여도 인구당 부족), 보육 102%·초등 85%→보통, 의료 979%·문화 607%→많음. ★간판의 가장 약한 고리(개수 휴리스틱)를 재현가능 1인당 벤치마크로 교체. LLM 0(환각 불가)·여전히 '참고'·판단은 사람. 프론트 C탭 "(반경 실인구 1만명당·공급판정 기준)" 표기. 테스트 `test_cross_rules_radius_density_is_primary`(개수↔밀도 정반대 판정 가드).

---

## 8.8 D1 — 읍면동 해상도 옵션 ✅ 완료 (2026-06-30)

"구 단위는 너무 포괄적"을 해소. 모드 A(`/analyze`)·수급진단(`/diagnose`) 수요(demand)를 **행정동 단위**로도 산정. 데이터 없는 지표는 추정 않고 시군구로 폴백 + 정직한 note (절대 원칙 3·4). 전국 작동.

**핵심 발견** — 현행 `DT_1B04005N`의 실제 KOSIS 제목이 **"행정구역(읍면동)별/5세별 주민등록인구"** 다. 지금까지 같은 표에 시군구 5자리 코드(`objL1=sgg_code`)를 넘겨 구 합계만 받았을 뿐, 표 자체가 **읍면동 3620개**를 담고 있다(실측). 읍면동 지역코드 = **카카오 `coord_to_hcode` 행정동 H코드(10자리)와 정확히 일치**(`1156054000`=여의동). 8자리·법정동은 err21 → 10자리 H코드만. → 인구·연령 5지표는 **새 인프라 0**으로 동 단위 가능.

**동 가능/불가** (실측):
- **가능**(DT_1B04005N, reg-scheme): 총인구수·고령인구비율·유소년인구비율·생산가능인구비율·노년부양비.
- **불가→구 폴백**: 1인가구비율·평균가구원수(census `DT_1JC1511`은 시군구만, 최신 읍면동 표 없음) · 순이동(reg지만 미검증) · **세대수(★KOSIS 읍면동 없음 확정 — 시군구 `DT_1B040B3`만; 읍면동 세대는 행안부 rdoa=`services/jumin.py`로 해결, §8.13)** · 대기질(측정소 기반).

**구현**:
- `matrix.json _meta.dong_tables`=`["DT_1B04005N"]`(검증된 reg-scheme 표만). `matrix.dong_tables()` 헬퍼. 표 추가 시 JSON만 수정(절대 원칙 7).
- `kakao.coord_to_hdong(lat,lon)`→`{code(H10),name(행정동명)}`. 라우터가 **읍면동 요청 시에만 lazy 조회**(다른 엔드포인트 성능 무영향).
- `stats.collect_facts`/`collect_facts_by_items`에 `resolution`·`hcode`·`hdong` 파라미터(기본 "시군구" → compare·readout 하위호환). `_collect_kosis_facts`가 그룹별로 `resolution=='읍면동' and scheme=='reg' and tblId in dong_tables` 면 H코드로 조회, 아니면 구 폴백+note.
- **fact별 `scope`/`scope_level` 추가**(데이터 계약, §6 Fact). 동 모드에선 facts가 섞이므로(일부 동·일부 구) 전역 "○○구 기준" 대신 **수치마다 기준 표기**(절대 원칙 4). `DemandSignal`에도 동일. `narrative`는 scope 혼재 시 "여의동 단위 지표를 제외한 나머지는 영등포구 기준"으로 정직하게 서술.
- 프론트 A·C탭에 "분석 단위(구/동)" 토글 + facts 표에 '기준 지역' 컬럼.
- 검증: 여의동 총인구 34,066·고령 20.6%(구 19.2%)·유소년 11.0%(구 8.3%) 실데이터. 단위테스트 4(`test_dong_resolution.py`, monkeypatch 네트워크 0), 기존 회귀 통과.

**D2 예고** — 진짜 "반경 인구"는 통계청 **SGIS 집계구**(약 500명 단위)로 좌표+반경 실인구를 합산(모드 B와 같은 패러다임). 구 평균을 면적비례로 쪼개는 보간은 **금지**(원칙 1·3, 해석). SGIS 무료 키 대기 중.

---

## 8.9 D2 — 진짜 반경 인구 (SGIS 집계구) ✅ 완료 (2026-06-30)

수급진단(`/diagnose`)의 **demand를 진짜 반경 내 실인구**로. 공급(반경 시설개수)과 **같은 반경 단위** → "단위 다름" 한계(§8 P11) 해소. 구 평균을 면적으로 쪼개는 보간은 **금지**(원칙 1·3) — 통계청 SGIS **집계구**(약 500명 단위) 실인구를 합산한다. 전국 작동. 상세 엔드포인트는 메모리 [[sgis-radius-population-api]].

**SGIS 키** — `.env` `SGIS_KEY`(consumer_key)+`SGIS_SECRET`(consumer_secret) 2개. 호스트 `https://sgisapi.mods.go.kr/OpenAPI3`. accessToken 발급(만료 epoch ms까지 캐시) 후 호출.

**반경 인구 4단계** (`services/sgis.py fetch_radius_population`, 실측 확정):
1. 좌표 WGS84 → UTM-K(5179) `transformation/transcoord` (SGIS 경계는 전부 UTM-K 미터).
2. 반경 bbox → `boundary/userarea.geojson cd=4` → 집계구 폴리곤+중심좌표(14자리 adm_cd) → 반경 원 필터.
3. 집계구 → 읍면동(앞8자리) 그룹 → `stats/population.json adm_cd=<8자리> low_search=1` → 그 읍면동의 집계구 전체가 `tot_ppltn`·부양비 등과 함께(집계구 직접조회는 -100, **읍면동 low_search=1로 펼쳐야** 나옴).
4. 반경 집계구 `tot_ppltn` 합산 + **부양비 역산**으로 연령비율.

**연령비율 역산** — 집계구는 연령대별 인구수를 안 주지만 `juv_suprt_per`(유년부양비)·`oldage_suprt_per`(노년부양비)는 준다. `W=tot/(1+J/100+O/100)`, `youth=W·J/100`, `old=W·O/100` (표준 0-14/15-64/65+). 집계구별 인구수를 역산·합산해 재계산 → 보간 아닌 정확 산술. 부양비 결측 집계구는 총인구엔 포함·연령비율 모수 제외(note).

**연결** — `resolution="반경"`(region.py Resolution에 추가)을 **`/diagnose`·`/analyze` 둘 다** 지원.
- **/diagnose**: demand 3지표(유소년·고령·생산가능인구비율)를 SGIS 반경값으로 교체(national_avg는 KOSIS 전국값 유지). 수요·공급 같은 반경. 1인가구비율은 SGIS 미제공→시군구 폴백+note.
- **/analyze**: `AnalyzeRequest.radius`(기본1000). 인구/연령 facts(총인구·고령·유소년·생산가능)를 SGIS 반경값으로 교체 + **인구밀도(명/㎢, 반경 πr² 면적 기준)·평균나이** 신규 fact(KOSIS 시군구엔 없던 값). 가구·대기질 등은 시군구 유지(`router _apply_radius`). narrative `_scope_disclaimer`가 반경·동·구 혼재를 정직 서술.
- 공통: region.resolution="반경", name="○○구 반경 Nm". fact별 scope/scope_level="반경". SGIS 실패 시 graceful 시군구 폴백. 프론트 A·C탭 "반경(집계구)" 토글(+A탭 반경 선택기).

**검증(여의대로24)**: 500m=집계구7개·3,635명. 1km=62개(60매칭)·29,281명·유소년5.6%·고령16.1%·생산78.2%·인구밀도9,320명/㎢·평균나이42.5세(1km는 금융지구 포함→동단위 11%보다 유소년 낮음=반경 정밀도). 미매칭 집계구(한강·공원 무인구)는 note. 테스트: 비라이브 4(diagnose 2·analyze 2 monkeypatch)+라이브 2(`test_sgis_live.py`). `verify_apis.py probe_sgis` 추가.

---

## 8.10 안전·재해 컨텍스트 레이어 (SGIS 위험지도) ✅ 완료 (2026-06-30)

대지의 **재해위험 사실**을 `/site`에 추가 — 홍수·산사태 위험지도 **영향범위에 대지 읍면동이 포함되는지(Y/N)**. 수급진단(demand×supply)이 아니라 **독립 컨텍스트 레이어**다 — 위험은 수요/공급이 아니므로 억지로 수급에 넣으면 차별점 게이트(§2)에 걸린다. "규제·물리 위험 사실을 수치로 제시"(§3 우리가 하는 것)에 해당. 등급·심도 판단은 안 하고 포함 여부 사실만 (절대 원칙 5). SGIS 키 재활용([[sgis-radius-population-api]]).

**메커니즘**(`services/sgis.py fetch_site_hazards`, 실측 확정):
- 좌표 → `boundary/userarea cd=3` → **census 읍면동 8자리**(시군구=앞5자리). SGIS는 census 코드(경기=31·영등포=11190).
- `ndsm/floodRiskAdmCdList.json`·`ndsm/lndsldWarnAdmCdList.json` `adm_cd=<census 시군구>` → **위험 영향범위에 든 읍면동 목록** → 대지 읍면동 포함 여부 판정(보간 아님 — 위험지도가 지정한 행정구역).
- **영향범위 내 지표**(#83 `floodRiskDataBoard`·#85 `lndsldWarnDataBoard`, `_hazard_exposure`): iem_nm **인구·가구·주택·사업체·노후건물·지하건물**(지하·노후=침수 직결) 총합의 영향구역/행정구역(`HazardZone.exposures[]`={metric,affected,total,unit}). **읍면동 우선·일부 동/재해는 HTTP 500 → 시군구 폴백**(`exposure_scope` 기록).
- **폭염특보 이력**(#86 `prevHwSpcnwsList`, `fetch_heatwave_history`): 최근 여름 폭염 경보·주의보 발효 건수. ★데이터는 **2024~2025만**(이전 -100). 특보구역=서울 4권역·비서울 시군구 → up_spcnws_zone_nm(시도) 매칭, 시군구 구역명 있으면 좁힘(`scope`). 각 행=종료된 특보 1건(전부 '해제') → 레벨별 카운트.
- 결과: `flood{in_zone, affected_dong_count, exposures[], exposure_scope}`·`landslide{...}`·`heatwave{alert_count, warning_count, scope, base_period}`·base_year. graceful.

**검증**: 여의도=홍수✅(영향 인구3,840·가구1,863·주택1,762·사업체905·노후건물52·지하건물71, 읍면동)·산사태✅(시군구폴백)·폭염(경보11·주의보31, 서울권역). 강남역=홍수✗·산사태✅(우면산). 춘천=둘 다✗·폭염경보4·주의보44. `/site` `hazards`, 프론트 F탭(포함=amber·외=green, 지표별·폭염건수). 라이브 테스트 `test_sgis_live`(membership·heatwave), `verify_apis probe_sgis`.

**확장 여지**: 폭염 영향예보(#87 ifarea 보건취약 등)·태풍(#79~81).

---

## 8.11 S 시리즈 — 대지 종합 읽기 + 해석/판단 분리 📋 계획 (2026-06-30 설계 확정, 미착수)

흩어진 출력(/analyze·/diagnose·/site·/seed)을 **하나의 일관된 "이 필지는 어떤 곳인가"**로 합성. 목표 = 포괄적 분석 + 더 좋은 해석, **환각·과장 0** 보증. 핵심 아이디어: **사실(코드가 연결) → 그 위에서 AI 표현**, 그리고 **해석과 판단을 벽 쳐서 분리**.

### 단계 (각각 독립 완료 가능, S1부터)

- **S1 데이터 근접도 레이어** ✅ 완료 (2026-07-09) — 모든 fact/signal에 `proximity` 등급 통일: `대지(필지) > 반경 > 읍면동 > 시군구 > proxy/추정`. 기존 scope_level을 한 축으로 정규화. "구 평균은 대지값 아님" 원칙이 모든 출력에 기계가독·정렬가능하게 박힘. 순수 메타데이터 → 환각 0.
  - **구현**: `app/schemas/proximity.py` (`Proximity` Literal + `PROXIMITY_ORDER` 정렬순 + `proximity_of(scope_level)` 매퍼 + `proximity_rank()`). `Fact`·`DemandSignal`은 `model_validator(mode="after")`가 `scope_level`→`proximity` 자동 유도(호출부 무변경 — 명시 override는 존중). `SupplySignal`은 개수가 항상 반경 실측이라 기본 `proximity="반경"`(capacity만 시군구, capacity_scope로 구분). 근접도는 *지리적 해상도*이지 지표 품질이 아님 — 문화시설 수요를 생산가능인구비율로 대신하는 '대리 지표'는 proxy로 낮추지 않음. 현재 producer 최상급은 반경(대지값은 /site 필지데이터라 S3 통합 풀에서 부착 예정 — 등급은 완결성 위해 정의). 프론트 A탭(기준 지역·근접도 컬럼)·C탭(수요·공급 칩)에 `ProximityChip`(ui.jsx, 등급별 tone). 테스트 `test_proximity.py` 8건. 회귀 71 통과.
- **S2 교차규칙 엔진** ✅ 완료 (2026-07-09) — `cross_context.json` 신설. implications.json 패턴을 **도메인 횡단**으로 확장. 통합 fact 풀(인구+수급 signal+재해)을 읽어 근거(basis) 달린 '참고' 시사점 생성. 예: 고령↑+의료수급 적음→"의료 접근성 검토" / 홍수영향+지하건물↑→"지하 침수 대비 검토" / 1인가구↑+폭염 빈발→"취약계층 폭염 대응 검토". **전부 규칙 매칭, LLM 0, 새 숫자 안 만듦**(기존 fact 값 boolean 조합).
  - **구현**: `app/services/cross_context.py`(`derive_cross_context(facts, diagnoses, hazards, use_type)` 순수 엔진 — Fact/Diagnosis/SiteHazards 또는 dict 공용). `app/data/cross_context.json`(규칙 7개: 의료 접근성·보육 인프라·문화 인프라·지하 침수·노후건물 침수·취약계층 폭염·복합 재해). `app/schemas/cross_context.py`(`CrossImplication`·`CrossBasis`). 절(clause) 종류: `pop`(인구 fact vs national/절대값)·`supply`/`demand`(수급진단 level)·`hazard`(영향범위 포함)·`hazard_exposure`(영향 지표 개수)·`heatwave`(특보 건수). **한 규칙의 `when` 절이 모두 참일 때만 발화**, 하나라도 확인불가(national_avg None·지표 없음)면 미발화(추정 안 함, 절대 원칙 3). `domains`는 절 종류에서 자동 유도. **각 basis 에 값 그대로 인용 + S1 proximity 부착**(근거의 대지 근접도 투명, 절대 원칙 4 — 광역 폭염특보는 proxy). 테스트 `test_cross_context.py` 10건(실제 객체 형태 3예시 + 경계·필터). **S2 는 순수 엔진 — 통합 풀 조립·엔드포인트 노출은 S3(/board)의 몫**(중복 방지, 아직 미배선).
- **S3 `/board` 통합 진입점** ✅ 완료 (2026-07-09) — 기존 서비스(analyze·diagnose·site·seed) **재사용·병렬 오케스트레이션**(새 데이터 0). 한 객체: 공유 site + 도메인별 facts(근접도 부착) + 수급진단 + 재해 + S2 교차시사점 + **결측/확인불가 목록**(no silent skip). 프론트 종합 탭.
  - **구현**: `app/routers/board.py`(`POST /board`) + `app/schemas/board.py`(`BoardRequest`·`DomainCoverage`·`BoardResult`). 주소 1회 fail-fast 해석(`build_site` — 공유 Site·PNU) 후 **4개 도메인 브랜치**(analyze·build_diagnosis·site_info·seed)를 `ThreadPoolExecutor`로 병렬. `_run` 헬퍼가 예외·에러응답(JSONResponse) 둘 다 graceful 흡수 → 에러 message 를 notes 로 이관(부분 실패 격리·투명). 각 브랜치에서 **조각만 뽑아 담고**(facts·implications·region / diagnoses / hazards·land_price·building·real_estate / context) 재계산 안 함. 그 위 **S2 `derive_cross_context(facts, diagnoses, hazards, use_type)` 호출**(★ 교차시사점). `coverage`=도메인별(인구·수급·재해·대지·생활맥락) 확보 여부+사유(no silent skip). **종합점수·순위 없음**(P9 원칙). 프론트 **I탭 "종합 읽기"**(TabI, 앱 첫 탭·flagship): coverage 그리드 + ★교차시사점(근거·근접도 칩) + 함의·수급요약·대지. 테스트 `test_board.py` 4(monkeypatch로 4브랜치 대체·실제 S2 발화·coverage·부분실패·하드블록). ⚠️ 4브랜치가 각자 resolve/SGIS 중복 호출(병렬·graceful이라 무해하나 최적화 여지 — 공유 resolve/토큰은 후속).
- **S4 종합 산출 = 두 블록 (벽 분리·라벨)** ★ ✅ 완료 (2026-07-09) — S1~S3 구조물 위에서:
  - **① 사실 종합 (해석)** — 그라운디드. 실수치만·모든 문장 fact 추적·근접도/출처 명시·'참고'. "이 필지는 ~한 곳" 특징서술. **모델 Sonnet(claude-sonnet-5)**(서술, 싸고 충분·effort low). P6 narrative 패턴.
  - **② AI 판단 (의견)** — 명확히 분리·라벨("아래는 AI 의견·검증/재현 보장 없음·최종결정은 사람"). 용도 관점 적합신호(±)·종합 의견. **조건: (a) 근거 fact 인용 (b) 가정 명시 (c) 새 숫자 안 만듦**. **모델 Opus(claude-opus-4-8)**(추론 정교·adaptive thinking·effort medium).
  - 둘 다 Claude(원칙 6 유지)·2콜·그라운디드·규칙 폴백. **OpenAI 불필요**(한국어 도메인 그라운디드 합성은 Opus/Sonnet 최상급·병목은 모델 아닌 그라운딩 구조·다벤더는 잡음).
  - **구현**: `app/services/synthesis.py`(`synthesize(use_type, facts, diagnoses, hazards, cross)` → `Synthesis`). `compose_interpretation`(①,Sonnet)·`compose_judgment`(②,Opus)·`_pool_text`(풀→그라운딩 텍스트, 근접도·출처 포함). **라벨은 코드가 항상 부착**(`JUDGMENT_LABEL`, 모델에 안 맡김). **그라운딩 사실 없으면 `no_data`**(환각 금지, 절대 원칙 3). 폴백: 키없음·오류·refusal → ①규칙서술·②'판단 유보'(가짜 의견 안 만듦). `POST /board`에 **`synthesize:bool=False` opt-in**(기본 off — Claude 2콜이라 느림), `BoardResult.synthesis`. 프론트 I탭 "AI 종합 해석 생성" 체크박스 + **벽 분리 렌더**(①green 검증된 사실·②amber AI 의견+⚠라벨). 테스트 `test_synthesis.py`(규칙폴백·no_data·라벨·풀텍스트, 비네트워크). **실API E2E 검증**(여의도 풀): ①Sonnet=시군구 단위 명시·수치만·참고 / ②Opus=3조건 준수(근거 인용·"~가정하면"·"별도 확인 필요"·"최종 판단은 사업 주체 몫", 금액 단정 0). §2.5·§2.6 문구 갱신 완료.

### 정직성을 지키는 핵심 = 분리 + 라벨

위험은 "의견이 사실인 척하는 것". **벽 + 라벨**로 "검증된 사실(①)"과 "AI 의견(②)"을 사용자가 절대 혼동 안 하게 → 숨기지 않으니 오히려 더 투명. 판단 블록도 그라운딩(새 숫자 금지)은 유지.

### ⚠️ 원칙 변경 (S4 착수 시 적용) ✅ 적용 완료 (2026-07-09)

이 설계는 **§2.5(판단은 사람) → "판단은 분리·라벨해 제시하되 *최종 결정*은 사람"으로 완화**했다(§2 원칙 5·6 문구 갱신 완료). S1~S3 단계는 이 완화와 무관(사실·메타·규칙뿐)이었고, S4에서만 AI 판단 블록을 3조건(근거 인용·가정 명시·새 숫자 금지)+코드 부착 라벨 하에 추가.

### 함정 (착수 시 점검)

- 판단 블록 문구가 "검토 사항/신호"를 넘어 "사업성 N억·반드시 ~하라"로 가면 환각·검증불가 → 라벨·가정·fact인용 3조건 강제.
- 근접도 등급이 거짓이면(구 평균을 대지값으로 둔갑) 차별점 붕괴 — 등급 정직성 최우선.
- /board는 오케스트레이션만, 데이터·숫자는 기존 서비스에서(중복·재계산 금지).
- 종합점수·순위는 안 매김(P9 비교 원칙 유지) — 판단 블록도 서술형 의견이지 스코어 아님.

---

## 8.12 T 시리즈 — 신뢰(Trust) + 활용(Translate) 🟡 진행중 (2026-07-09 설계, T1 완료)

"임원·실무자가 믿고 실제 설계·제안서에 쓸 수 있는가"를 닫는 트랙. 상용 제품 3종 심층조사(Local Logic·Esri Business Analyst/Tapestry·한국 랜드북/밸류맵/토지이음)로 근거를 잡음.

**조사 3대 결론:** ① 우리 엄밀성(출처·근접도·확인불가·S4 벽)은 이미 상용 이상 — 빠진 건 *포장·번역*뿐. ② 상용 공통 문법 = 정규화 지수(전국=100)·근거 드릴다운·지도앵커·공유링크>PDF>API. ③ **"이 동네니 설계는 뭘 해야"(드라이버·프로그램)와 수요×공급 교차는 어디에도 없음 = 우리 blue ocean.** 결정: 도메인별 지수 O·단일 종합점수 X(원칙5 유지), 딜리버리 3종.

- **T1 정규화 지수 + 근거 드릴다운** ✅ 완료 (2026-07-09). `Fact`·`DemandSignal`에 `index`(전국=100 = value/national×100, **비율 지표만** — 절대수·national없음은 None, 오지수 방지)·`index_band`(상회|비슷|하회, ±10%). **순수 비율일 뿐 새 숫자 아님**(절대 원칙 2). `region.compute_index`/`index_band` + model_validator 자동유도(호출부 무변경). 프론트 `ui.jsx IndexBar`(100 중심·방향으로 상회/하회·중립색=판정 아님), A탭 "전국 대비(100)" 컬럼 + **fact 행 클릭→근거 드릴다운**(값·전국·지수·기준지역·근접도·출처·연도 = Local Logic "점수→근거" UX), C탭 demand 지수 노출. 테스트 `test_index.py` 8(경계·게이팅·자동유도)+회귀 46 통과, 빌드 40모듈.
- **T1.5 대지 아키타입** ✅ 완료 (2026-07-09) — Esri Tapestry식 "이 동네는 ○○형". ⚠️ K-means(통계 클러스터=해석) 금지 → **결정론 규칙 룩업**(원칙1). 구현: `services/archetype.py`(`classify_archetype`), `data/archetype_rules.json`(유형 8종·2계층 group·signals·min_match, 건축가 편집), `schemas/archetype.py`(`Archetype`·`ArchetypeEvidence`). 유형: 고령 정주형/1인가구 도심 임대권/육아·가족 정주형/인구 유출 관망지/인구 유입 성장지/생산연령 밀집 도심/저지대 침수 민감지/사면 인접 산지형. signal 종류 pop(index 상회/하회)·fact(원시값 임계)·hazard(in_zone)·supply(수준). **지배 유형 1개(match_score 최고)+alternatives(차점), 강한 매칭 없으면 '혼합형' 폴백, 풀 없으면 None**(억지 분류 금지·원칙3). **LLM 0·새 숫자 0**. `/board.archetype`+board_brief+synthesis 풀(S4가 "이 동네는 ○○형" 오프닝)+board_view/TabI 헤드라인 렌더. test_archetype 6. 검증 여의도→"1인가구 도심 임대권"[주거·1인] score 2.0(1인가구 지수125+평균가구원수2.0), 차점=유출/침수/사면. 회귀 72 통과. 아티팩트 갱신 c5a8d35f.
- **T2 설계 드라이버 합성** ✅ 완료 (2026-07-09) ★ — 통합 풀(인구 지수+수급 signal+재해)을 **증거강도로 랭킹** → 지배 드라이버 2~3개("분석의 종착점=design driver", 리서치). **상용 아무도 없음 = blue ocean.** 구현: `services/design_drivers.py`(`derive_design_drivers`), `data/driver_rules.json`(드라이버 7종·signal·가중치·임계, 건축가 편집), `schemas/design_drivers.py`(`DesignDriver`·`DriverEvidence`). signal 종류 pop(fact.index 상회/하회, 강도=\|index-100\|/10×근접도)·supply/demand(수준×근접도)·hazard(in_zone)·hazard_exposure·heatwave. strength=가중합, min_strength/max_drivers/proximity 가중 JSON. **LLM 0·새 숫자 0**(기존 지수·수준·in_zone 가중합만). 각 드라이버=name+response(검토 신호)+strength+evidence(값·근접도 인용)+'참고'. **드라이버는 재료, 제안서 컨셉안은 형제앱(competition) 영역**(경계). `/board.design_drivers`, S4 synthesis 풀에 편입(`_drivers_block` → ①②가 근거로 활용). 프론트 I탭 "설계 드라이버" 섹션(랭킹·응답·근거칩, 헤드라인). test_design_drivers 8(랭킹·강도산술·게이팅·필터). 검증(여의도): #1 방재 4.0 > #2 접근성 3.7 > #3 공용완충 3.6. 회귀 66 통과.
- **T3 프로그램 함의(POR)** ✅ 완료 (2026-07-09) ★ — 맥락→**건축 카테고리별 공간·프로그램 권고**(대지·배치/저층부/평면·세대/코어·동선/공용부/방재·설비/조경·외부) = Program of Requirements 체크리스트. **상용 아무도 없음 = blue ocean.** 구현: `services/program.py`(`derive_program`), `data/program_rules.json`(규칙 8·카테고리·when+items, 건축가 편집), `schemas/program.py`(`ProgramItem`=category+recommendation+basis). **절 매칭(AND)·근거는 S2 `cross_context._eval_clause` 재사용**(중복 0) — when 모두 참이면 items 방출, (카테고리,권고) 중복은 basis 병합, 카테고리 순 정렬. **LLM 0·새 숫자 0**(원칙 1·2). S2(왜)·T2(지배 신호)와 구분: T3=**"무엇을, 어느 카테고리에"**. `/board.program_implications`+board_brief(competition 제안서용)+board_view/TabI 카테고리 그룹 렌더. test_program 6. 검증 여의도(주거)→9~11항목: [평면] 소형평형 [코어] 무장애 [공용부] 공유주방·쉼터 [방재] 방수판·전기실상부 [대지] 지반고상향·사면배수 등. 회귀 51 통과. 아티팩트 c5a8d35f 갱신.
- **T4 대지분석 보드 + 딜리버리** ✅ 완료 (2026-07-09) — 지도앵커+커버리지+★설계드라이버+S4종합+지수막대+근접도칩+출처푸터 → **공유링크·인쇄(PDF)·API**. 구현: `services/board_view.py`(`render_board_html` — 자체완결 full HTML, 건원 레드 토큰·CSP-safe·오프라인, TabI와 동일 시각, `@media print`), `POST /board/view`(전체 board 빌드→HTML을 out/boards 저장→`/files/boards/*.html` 공유 URL 반환, `_satellite_anchor`가 VWorld 위성+반경링 JPEG data URI 상단 임베드·graceful). 프론트 I탭 "보드 내보내기 ↗" 버튼(새 탭·인쇄→PDF). **새 데이터 0**(BoardResult 렌더만). test_board_view 6(렌더·XSS-safe·지도임베드·엔드포인트·주소에러). 실호출 검증: 여의도 보드 175KB(위성지도 임베드)·has_map True. 아티팩트 데모 claude.ai/code/artifact/c5a8d35f. 리서치("편집된 한 장·지도 앵커·provenance in export") 반영. **딜리버리 3종 완비: 대시보드(I탭)·API/MCP·공유보드.**
- **T5 방법론·데이터 부록** ✅ 완료 (2026-07-09) — 이 보드의 수치가 **어디서·어떻게** 나왔는지 자동 부록(Esri 방법론공개·토지이음 확인원 방식). 공공 공모·감사 대비. 구현: `services/methodology.py`(`build_methodology(board)`), `data/methodology.json`(출처 카탈로그 20종·산정식 9·도메인→출처 매핑, 건축가 편집), `schemas/methodology.py`(`Methodology`=summary+resolution+`SourceEntry[]`+`FormulaEntry[]`+limitations). **BoardResult 에 이미 흐르는 출처(fact.source_tbl·source_type·presence)를 레지스트리와 조인만 — LLM 0·새 숫자 0**(절대 원칙 1·2). **기여한 출처만** 담음(no silent inclusion): fact→`_match_source`(KOSIS 표ID·`에어코리아`접두·`SGIS 집계구`정규화)·재해/대지/생활맥락→presence. **미등록 출처는 지어내지 않고** 원시 키+'미등록' note(절대 원칙 3). 산정식=등장한 파생지표만(고령/유소년/1인가구비율·노년부양비 + 조건부: 전국=100 지수·반경 인구·부양비 역산·공급밀도). 한계=평균값 캐비엇+확인불가 도메인(coverage)+수급 휴리스틱. `/board.methodology`(항상 계산, 비용 0)·board_view/TabI 부록 섹션(출처 표·산정식·한계). test_methodology 10(매핑·presence·미등록 폴백·산정식·한계·통합). 회귀 148 통과, 빌드 40모듈. **T 시리즈 T1·T1.5·T2·T3·T4·T5 전부 완료.**

**추천 순서:** T1→T2→T4→T1.5·T3→T5 **전부 완료(2026-07-09)**. **금지선 유지:** AI 렌더·자동 매싱·수익률 추정 안 만듦(랜드북·Forma 레드오션·환각 위험). 우리는 "지어내지 않는 근거 + 설계 번역 + 정직한 포장".

### 형제앱 연동 (D:\APPS 생태계) — 2026-07-09 조사·계약·MCP 완료

20개 형제앱 조사 결론: **중복 사실상 0**(형제=설계 산출물/법규, 우리=설계 전 대지 인문맥락). 최강 시너지 = **competition_comparison**(설계공모 제안서 자동생성 — 지금 대지분석을 VWorld vision 추론으로 부실하게 함, 우리 /board 실측 주입 시 상상→실측·우리 T시리즈의 "출구"). 2위 = **arch-site-model**(주소→물리 3D 지형/건물, 입력동일·산출정반대·완전한 보드 반쪽). 상세 조사·시너지는 [[project-phase]] 메모리.

- **원칙: 터읽기는 provider — 형제를 호출하지 않는다.** 조립은 소비자(competition)·허브 파이프라인(kw-ai-hub)·Claude(MCP)가.
- **연동 2단계 계약 확정** ✅ (2026-07-09). `/board`=표준 페이로드(`schema_version:"board/1.0"`). `brief=true`→압축 투영(`board_brief/1.0`, ~66KB→~7KB, 원시 seed context 제외·해석층만) 제안서·MCP·주입용. `services/board_contract.py`(`board_brief`·`board_to_project_seed`—law/knowledge 슬롯 형제앱에). `ProjectSeed.schema_version`. INTEGRATION.md §4 갱신. test_board_contract. **경계: brief는 ①② 다 담되 competition은 ②AI판단 제안서 직접전재 금지**(이중 의견·출처흐림).
- **연동 3단계 MCP 서버** ✅ (2026-07-09). `mcp_server/server.py`(FastMCP, law-qa 패턴) — 도구 `read_site_context`(→board_brief)·`diagnose_supply`(→수급진단). 기존 서비스 얇게 래핑(로직변경 자동반영). `.mcp.json`(venv python). **개별(Claude Desktop/Code에서 한 줄 호출)·파이프라인(에이전트 조립) 둘 다.** `mcp>=1.2` 의존성. test_mcp_server(래핑 로직 monkeypatch). `claude mcp add teoilgi python mcp_server/server.py`.
- **연동 4단계 competition 연동** ✅ 완료 (2026-07-09) — competition_comparison(형제 레포)이 `POST /board {brief:true,synthesize:false}` pull → 수주 제안서 "대지분석·site_rationale·design_directions"를 vision 추론→**실측**으로 격상. 형제 레포 변경(surgical·graceful): `services/teoilgi_client.py`(신규, `fetch_board_context`·`FACILITY_TO_USE_TYPE` 매핑 14종→주거/상업/의료)·`routers/brief.py`(_site_context 에 vision + **measured** 병합, VWorld 키 무관·독립)·`services/brief_proposal.py`(`_measured_digest`로 payload.site_context.measured + 프롬프트 "정량·사실은 measured 우선·design_drivers 연결·basis에 measured.키·새 숫자 금지"). **경계 준수: synthesize=false → 우리 ②AI판단 미전달**(competition이 자체 Opus로 제안서 작성). 검증: competition venv 신규 test 6 + 기존 399 무회귀, **실HTTP E2E**(competition client→우리 /board→4.2KB 다이제스트: 드라이버 방재5.0·공용완충4.0·사면3.0·지수·재해·공시지가, ②AI판단·notes 미유출 확인). **추천 시퀀스(T2→계약→MCP→competition) 4칸 전부 완료.**
- **연동 5단계 arch-site-model 결합** ✅ 완료 (2026-07-09) — **물리 3D + 인문 = 완전한 보드.** arch-site-model(형제, `POST /api/generate`)이 주소→물리 3D(건물·터레인·지적 geometry + `.3dm/.skp` + `origin_offset`)를 냄. **정합성**: 두 앱이 같은 주소 진입·**같은 PNU**(VWorld `LP_PA_CBND_BUBUN`)·같은 VWorld 를 씀 → site 만 공유하면 한 보드의 양쪽(입력동일·산출정반대). **방식=계약 확장 + 받은 모델 렌더**(사용자 결정): **터읽기는 arch-site-model 을 호출하지 않는다**(provider 경계 유지) — assembler 가 넘긴 출력을 `summarize_model`로 요약·렌더만. 구현: `schemas/site_model.py`(`SiteModelSummary` — 압축: building_count·elev_range·origin_offset·footprints≤400·files·provenance)·`services/site_model.py`(`summarize_model(raw)` 방어적 추출, 원시 terrain 미보관·새 숫자 0)·`schemas/project_seed.py`에 **`model` 슬롯**(law·knowledge 대칭, 형제앱 소유 느슨 dict)·`board_contract.board_to_project_seed(...,model=)`. `BoardRequest.model`(assembler 입력)→`BoardResult.model`. **`board_view` 축측(axonometric) 매싱 미리보기**(`routers/board._massing_anchor` — geometry 로컬미터 이소 투영 2:1·painter 정렬·PIL, **three.js 없이 서버사이드** = 보드 자체완결·오프라인 유지, 위성 앵커 패턴) + 물리모델 섹션(통계·다운로드). 프론트 I탭 물리모델 패널. test_site_model 9(요약·방어·상한·계약·/board배선·매싱렌더·섹션). 회귀 무회귀·빌드 40모듈. **검증: 36동 합성 모델→축측 매싱 46KB 실렌더**(도시 블록 3D). **경계: 우리는 호출 안 함 — 조립은 assembler(competition·kw-ai-hub·Claude).**

---

## 8.13 심의 현황팩 (건축경관심의 도서 자동화) 🟡 진행중 (2026-07-12)

서울시 건축경관심의 도서의 "조사·현황·기반시설" 파트(손 제일 많이 가는 조사 노동)를 자동 생성하는 트랙. 계기: 실제 심의도서(동작구 본동 441, PPT 271장) 대비 검토 → 슬라이드 5·118·119(주변현황도)·95·236·238·239(기반시설 충분성 = 도서관·어린이집·경로당 조사 + 행정동 인구·세대 + 총량제)가 터읽기(모드A·B·수급진단)의 정확한 타깃. 설계도면(평면·입면·배치…)은 경계 밖(형제앱·수작업). 상세 계획·진행은 메모리 `deliberation-pack-plan`.

**딜리버리 방향 (★):** flat PNG 아니라 **사용자 슬라이드를 템플릿으로 삼아 편집가능하게 채움** — 지도는 PNG 이미지(원래 슬라이드에도 그림으로 박힘), 표는 **네이티브 PPT 표 셀 채움**(python-pptx). 원칙 위반 0: 걸침비율=코드 기하(원칙1·2)·인구세대=실API(원칙1)·생활권 flag는 사람 확정(원칙5)·출처 라벨(원칙4).

**C1 조사범위 걸침 합산 — ✅ 엔진 완성·전국 실증:** 반경에 걸치는 행정동을 면적비율로 합산(심의의 실제 조사범위 방식). `kakao.resolve_coord` + `sgis.to_utmk` + SGIS `boundary/userarea cd=3`(읍면동 경계 UTM-K) + shapely 원 교차 = 걸침비율. × 인구·세대(행안부 rdoa) → 적용값 합산. **시군구 경계 넘는 행정동은 ⚠플래그(생활권 검토·사람 확정, 한강 하드코딩 없음).** 검증(슬라이드 238): 걸침비율 노량진1동 98.96%(심의 99.03%)·총인구 계 0.03%·총세대 계 0.04% 일치. 전국 실증(대전 서구 무수정 작동). shapely·numpy venv 설치. **→ 2026-07-14 `app/services/survey.py` 로 앱 이식 완료(아래 정본화).**

**jumin (행안부 rdoa) — ✅ 앱 배선 완료:** 읍면동 주민등록 **세대수**가 KOSIS OpenAPI엔 없음(시군구 `DT_1B040B3`만) → 행안부 주민등록 데이터개방 `rdoa.jumin.go.kr/openStats/selectConAdmmPpltnHh`가 행정동별 인구+세대를 **무키·전국·월별**로 제공. `app/services/jumin.py fetch_dong_stats(sgg_code5, ym=None)` — 세션(JSESSIONID)+hidden `paramUrl`+페이지네이션+HTML 결과표 lxml 파싱, (시군구,년월) 캐시, graceful. H코드 키 = `kakao.coord_to_hdong`과 동일. `requirements.txt` +lxml. `tests/test_jumin_live.py` 4개·`verify_apis probe_jumin`(무키). 전체 tests/ 215 passed. ⚠ REST 아님·HTML 스크래핑(§2 bus-factor) → 캐싱+구조변경 감지로 관리. 상세 메모리 `jumin-rdoa-population-household-api`.

**남은 것:** **✅ C1·C2·C4·C5·C6·C7 앱 배선 완료(2026-07-14, 아래 상세)** — `/context-pack`(+pptx)·`/surroundings`(+pptx) 라이브. C3 어린이집 형태(cpmsapi030 운영계정 전환 대기)만 잔여.

**★★C1·C2·C6 앱 정본화 완료 (2026-07-14):** scratchpad 프로토타입 → 앱 서비스로 승격. 15개 테스트 통과·실API E2E 검증.
- **C1 걸침 엔진** `app/services/survey.py`(`survey_area(address, radius, ym)` → `SurveyResult`): kakao 좌표 → SGIS 읍면동 경계(UTM-K)∩반경 shapely 걸침율 → 중심 transcoord → kakao H코드 → `jumin.fetch_dong_stats` 인구·세대 매칭 → 적용=총량×걸침율, 계=대지 시군구 포함분, 타시군구 ⚠flagged. `app/schemas/survey.py`. 실API 동작본동 재현(노량진1동 98.96%·적용세대 30,285). test_survey 2.
- **C2 총량제 엔진** `app/services/quota.py`(`compute_quota`/`compute_facility`) + **`app/data/community_quota.json`(5단계 세대규모 tier + confidence + 구조화 formula)**. tier 선택·fixed/formula·공공개방 ×1.2·부족(산출>0)/충족 판정. **★confidence=low tier(조례 변동 구간)는 판정 대신 "조례 확인 필요" note 자동 부착** — 하드코딩 오류 방지 코드화. `app/schemas/quota.py`. test_quota 7(동작 도서관 3471.34·경로당 −82.73·여의도 2000+ tier 416.76 실측 대조).
- **C6 오케스트레이터** `app/services/deliberation.py`(`assess_quota(address, new_households, ...)`): C1 걸침 → 구 영유아(KOSIS 0-4세)·구 세대(jumin 합) → **조사범위 시설 현황(아래)** → C2 판정. 다획지(new_households=list) 지원. graceful(구통계 실패 시 어린이집만 '확인필요', 추정 안 함). **`POST /context-pack`**(`app/routers/context_pack.py`, main.py 등록) → `QuotaAssessment`. test_deliberation 3 + test_context_pack 3. 실API E2E: 동작본동 981세대 → 도서관·경로당·어린이집 전부 부족시설 판정.
- **시설 현황 조사** `app/services/survey_facilities.py`(`collect_survey_facilities(lat,lon,radius,sgg)` → `List[FacilityCategory]`): 반경 내 도서관(카카오)·경로당(카카오+VWorld)·어린이집(카카오+cpmsapi021 정원) 목록·개수·주소·좌표·거리. `kakao.search_keyword` 에 `addr` 추가(하위호환). ⚠면적은 API 미제공(개별출처) → 목록·개수만. `QuotaAssessment.facilities` 에 편입. test_survey_facilities 2. 실API: 동작본동 도서관13·경로당32·어린이집10(정원2974). **→ 현황팩 데이터 축 완결(걸침·총량제·시설목록).**
- **★PPTX 산출 (C4·C5) `app/services/deliberation_pptx.py`** `build_pptx(assessment)` → **A3 편집가능 심의 현황팩**: ①걸침 인구세대표 ②시설 현황(위성 배경 그림 + 네이티브 반경원·번호핀 편집가능 위치도 + 현황표, 도서관·경로당) ③총량제 판정박스(부족=빨강/충족=초록). tiles.py 위성 재사용, 표·도형 전부 네이티브(사용자 손질). graceful(타일 실패→표만). **`POST /context-pack/pptx`** → OUT_DIR/packs 저장·`/files/packs/*.pptx` 공유 URL(board/view 패턴). SurveyResult/SurveyFacility 에 site_lat/lon·lat/lon 보강. test_deliberation_pptx 2. 실API E2E: 동작본동 981세대 → **A3 4슬라이드 1.9MB pptx 실생성**(위성 배경 포함). **★슬라이드 95·96을 주소+세대수만으로 통째 자동 생성 — 데이터+딜리버리 완결.**
- **프론트 심의 현황팩 탭 (C6·#3) `frontend/src/TabJ.jsx`** (App 탭 "심의 현황팩", api.js `contextPack`/`contextPackPptx`): 주소(공통)+신축세대(다획지 콤마)+반경 입력, [고급] 기존/계획 면적, 포함항목 체크리스트 → "산정하기"(걸침표·시설현황·총량제 판정 미리보기, 부족=amber/충족=green Badge·⚠조례확인) + "A3 PPTX 내려받기"(→`/files/packs` 열기). 빌드 41모듈 OK. **실 HTTP E2E**(uvicorn): 동작본동 981→site 11590·적용세대30285·시설{13,32,10}·판정[부족·부족·부족·면적기준]. 전체 pack 테스트 20통과. **★주라인 #1(시설현황)→#2(PPTX)→#3(프론트) 완결 — 주소+세대수 입력→심의 현황팩 A3 pptx 다운로드까지.** *(2026-07-13 기준 scratchpad 프로토타입으로 C1 걸침표·C2 총량제 판정박스·C4 위치도·C5 편집가능PPT(A3)까지 E2E 실증 완료 — 슬라이드 95·96 통째 재현. 상세 메모리 `deliberation-pack-plan`.)*

### 다음 타깃 — C7 주변현황도 (슬라이드 4~6) 자동화 계획 📋 (2026-07-13)

심의도서 앞부분 "주변현황도" 3장을 자동화. **핵심 = 슬라이드 5**(자동화 밀도 최고, C4 위치도·표 틀 재사용).

- **슬라이드 해부**: 4=사업개요표(설계값·경계밖)+광역현황도(공원·단지·학교·역·도로·재개발 라벨+방위+대상지) / 5=반경 250·500·750m 원+주변시설표(여가·교육·주거·관공서)+주변현황 서술+아파트세대수 / 6=이면도로 현장사진+도로폭(경계밖).
- **요소별 판정**: 🟢 위성·방위·대상지·반경원·**주변시설 카테고리표(공원·학교·아파트·관공서 카카오검색→네이티브표=홈그라운드)** / 🟡 지도 시설명 라벨(편집가능도형·80%자동+위치손질)·주변현황 서술문(우리데이터 룰기반 조립·LLM0)·아파트이름(세대수✗) / 🔴 **주변도로 폭원**(도로폭 소스 없음·도로명만)·**재개발/정비구역 경계**(소스 미확보)·**이면도로 현장사진**(경계밖)·사업개요표(설계값).
- **만들 범위(MVP)**: ①반경 250/500/750 현황도(카테고리별 색 핀·편집라벨) ②주변시설 카테고리표(네이티브) ③주변현황 서술문(반경 내 역·시설 개수 룰조립) + 보조로 광역현황도 주요라벨(학교·역·공원·단지) 자동배치. **제외**: 사업개요·이면도로사진·도로폭·재개발경계·세대수(억지 추정 안 함·절대원칙3, 빈칸/라벨자리로 사람이).
- **재사용**: `make_editable_map.py`(반경·색 확장)·`make_facility_tables.collect`(kind에 공원·학교·아파트·관공서 추가)·`make_combined_pack.py`(A3 조립). 거의 새 코드 0.
- **순서**: 카테고리 검색 확장 → 반경 현황도 → 카테고리표 → 서술문 룰조립 → A3 조립.
- **✅ C7 앱 배선 완료 (2026-07-14·#4)**: `app/services/surroundings.py`(`collect_surroundings(address,radius)` → `SurroundingsResult`) — 반경 내 교통·교육·여가·주거·관공서 카카오 수집 + **카테고리 코드 정제**(학교=SC4·지하철=SW8·공공기관=PO3, `kakao.search_keyword` 에 `category_group_code` 파라미터 추가) + **노이즈 토큰 필터**(행정실·후문·ATM 등)·이름 정제(단지 하위시설 합침) → 교육 60→6 실제 학교만. **서술문 룰 조립**(LLM 0, "반경 1km 내 지하철 노들역 인접·교육 6개소·공원 17개소·관공서…"). 설정 `app/data/surroundings.json`(카테고리·키워드·코드·색·narr). `app/schemas/surroundings.py`. **PPTX** `app/services/surroundings_pptx.py`(`build_surroundings_pptx` → A3 1슬라이드: 위성 반경현황도+카테고리 색점+범례겸 카테고리표+서술문). **`POST /surroundings`·`/surroundings/pptx`**(routers/surroundings.py). 프론트 **TabK "주변현황도"**. test_surroundings 2+test_surroundings_pptx 2. 실API 동작본동→교통3·교육6·여가17·주거10·관공서5 + 1.9MB 현황도 pptx. 도로폭·재개발경계는 소스 미확보로 표기 안 함(경계·원칙3).

### M드라이브 심의도서 전수 조사 결과 (2026-07-14)

회사 M드라이브 심의 PPT **3,448개** 발견 → 대부분 노이즈(소방·구조·조치계획·버전). 필터 후 **고유 통합심의 프로젝트 ~14개**를 **zip 슬라이드 XML 직접 파싱(미디어 스킵, 파일당 4초 — python-pptx는 수 분)**으로 스캔. `scratchpad/fast_pack.py`(zipfile+lxml, `ppt/slides/slide*.xml`만 읽음)·`simui_inventory.txt`.

- **현황팩 커버리지**: 서울 재건축·재개발·역세권 통합심의는 거의 전부 **걸침 조사 팩 보유** — 동작본동·삼익(강동)·노4(동작)·전농9(동대문)·여의도(영등포)·흑석11(동작)·목동6단지(양천)·천호우성(강동)·일원개포한신(강남)·고덕강일(강동). **단순총량제/없음** = 에코델타12·19(부산)·용인영덕·온수역세권·광교업무·광양(전남). → **걸침 방식은 서울시 통합심의 특유**, 우리 C1~C5의 정확한 시장.
- **★세대규모 tier 5단계 실측 완성**(`app/data/community_quota.json` 신설): 300~500 / 500~1000 / 1000~1500 / **1500~2000(천호우성·흑석11 — 계획했던 갭 실측으로 채움)** / 2000+(298·725 formula, 여의도·목동6단지). 총량 합계식도 tier화(100~1000: 세대×2.5×1.25 / 1000+: (500+세대×2)×1.25).
- **★핵심 교정 — 법정면적은 조례 변동값, 하드코딩 금지**: 300~500 도서관이 삼익='필수아님' vs 고덕강일=108㎡로 **충돌**(조례 개정·자치구·연도차). 어린이집 300~500도 198 vs 155 관측차. 1500~2000 경로당(500)이 1000~1500(580)보다 낮은 역전 관측 — 시설 매핑 확인 필요. → `community_quota.json`에 tier별 `confidence`(high/med/low)+`note`로 변동성 명기, 신규 프로젝트는 해당 조례 확인 후 조정. **산출 공식(예상인원 방식)은 안정적**, 법정 최소면적만 변동으로 취급.
- **✅ #5 조례 tier 법령 검증 (2026-07-14, 국가법령정보센터·법제처 웹검증)**: ①**총량 확정**=주택건설기준 §55조의2 (100~1000세대 세대당 2.5㎡ / 1000세대~ 500+세대×2㎡, ×1.25는 서울 심의 상향) ②**의무 세대수 확정**=경로당·놀이터 150~·어린이집 300~·**작은도서관·운동·돌봄 500~** ③**개별 세부면적은 §55조의2가 조례 위임 → 서울 주택조례 [별표1]**, 개정·연도별 변동값이라 심의도서 실측이 최선(우리 caveat 정확) ④경로당 산출식 50+세대×0.1 확인. **교정**: 작은도서관 300~500 = 108/low → **null(필수 아님)/high**(도서관 500세대~ 의무). `community_quota.json`에 `legal_basis` 블록 추가·boundaries 갱신. test_quota +1(300~500 도서관 None·경로당 198). 8통과.
- **정본화 대상 변형**: 걸침표 컬럼순서(총인구↔총세대)·용어(충족/충분/과다)·도서관표 주소 유무 → 출력 옵션으로 흡수. **신규 삽도 후보**: 용인고림H5BL '기반시설 분담계획도', '정비사업 통합심의 발표자료 서식'(표준 템플릿 파일 존재).

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

### ✅ 작동 확인 (10키)

KAKAO · VWORLD · KOSIS · JUSO · ANTHROPIC(claude-opus-4-8) · **KMA**(apihub, `authKey=`) · **RONE**(SttsApiTblData, `KEY=`) · **SEOUL**(INFO-000) · **NEIS**(schoolInfo) · **KOPIS**(`prfplc`) · **TMAP**(SK OpenAPI 보행자 경로, 앱 활성화 완료 2026-06-29). + OSM(무료, 이미 `facilities.py` 연결).

### 🟡 DATA_GO_KR — 키는 유효, 데이터셋별 승인이 갈림 (★중요)

- **판정 근거**: data.go.kr 는 *미승인 데이터셋*을 게이트웨이가 **403 Forbidden / 500 Unexpected**(평문)로 막음. *키가 틀리면* 표준 XML `resultCode=30`. 우리는 30이 아니라 403/500을 받았고 **동일 키로 7종이 정상** → 키 OK, 데이터셋 승인이 갈린 것.
- **작동**: 상가(상권)정보(B553077) · 응급의료기관(B552657) · HIRA병원(B551182) · 토지매매 · 연립다세대매매 · 아파트전월세 · 오피스텔전월세. **+ (2026-06-29 추가 승인 전파)** 아파트**매매** #33 · 건축HUB 건축물대장(`BldRgstHubService`) · 에어코리아 **측정값**(`ArpltnInforInqireSvc`, 단 측정소검색 `MsrstnInfoInqireSvc`는 여전히 403).
- **미승인(=코드는 있는데 실데이터 0)**: 표준지공시지가 #35(500, **VWorld로 우회 완료 — 불필요**) · 구버전 건축물대장 `BldRgstService_v2` #48(500, **건축HUB로 대체**) · 공장창고매매(403) · 경로당/마을회관(code30, **VWorld 검색으로 우회 완료**) · 어린이집(code30, **정보공개포털 cpmsapi021로 해결 — data.go.kr 불필요**) · 문화기반시설총람 B553457(**✅ 승인·연결 완료**, `services/culture.py`, 10종 operation).
- **영향 (대부분 해소됨)**:
  - ~~`services/airkorea.py`~~ → ✅ 해소: `getCtprvnRltmMesureDnsty`(승인됨)로 재배선, `/analyze` 대기질 4항목 실데이터(§9.1-3).
  - ~~`services/molit.py` + `/site`~~ → ✅ 해소: 공시지가=VWorld, 실거래 4종·건축물대장=승인 데이터(§9.1-1). `/site` §5 표 등재+테스트 완료.
  - 전부 graceful 처리라 앱은 안 죽음(절대 원칙 3 준수).

### 🔴 키/계정 미활성·인증실패 (사용자 액션 필요)

- ~~**TMAP #103**~~ → ✅ **해소** (2026-06-29): SK OpenAPI 앱 활성화 + Pedestrian Route API 구독 완료. `services/tmap.py` 배선(§9.1 항목 9).
- **LIBRARY #122**: "API 활성화 상태가 아닙니다" → data4library 계정 OpenAPI 활성화 승인.
- **CULTURE #134**: data.go.kr B553457 미승인(500) + kcisa(`API_CCA_###`) 401. ※ `API_CCA` 계열은 공연·전시 *콘텐츠*이지 시설총람 아님 → 진짜 #134는 **data.go.kr B553457(DATA_GO_KR키) 활용신청** 경로. 둘 중 하나 확정 필요.

### ⚫ SBIZ365 #29·#30 — REST API 자체 없음 (재분류)

소상공인365는 대시보드+파일(CSV/PDF)만. `SBIZ365_KEY`=포털용(fetch 불가). 매출/폐업/창업·빈상가는 **fileData 주기적 적재**가 유일 경로. 상권 실API는 이미 쓰는 data.go.kr B553077(점포분포)뿐 → §2 차별점 체크리스트 1번 불충족.

### ⬜ EUM(EUM_ID/EUM_KEY) — 범위 밖

규제정보 = arch-law-diagnose 담당(INTEGRATION.md §2, DEFERRED D6). 의도적으로 SKIP — 미검증 보류.

### 발견한 코드 버그

- ~~`app/services/airkorea.py`: getMsrstnList 서비스경로 버그~~ → ✅ **수정완료** (2026-06-29, §9.1-3). 측정소검색(`MsrstnInfoInqireSvc`)이 미승인(403)이라 아예 의존 제거하고 `getCtprvnRltmMesureDnsty`(시도 전체, 승인됨)+이름매칭으로 재배선.

### 다음 액션 (두 갈래)

- **(사용자) 포털**: ~~TMAP 앱 활성화~~ ✅ 완료. LIBRARY 활성화(또는 VWorld 도서관 검색으로 대체). data.go.kr 에어코리아 B552584 승인 확인.
- **(코드)**: ① 프론트에 /seed·/site 노출 ② KOSIS 미확정 지표(인구밀도·사업체수) 확정 ③ `verify_apis.py` 주기 점검 자산화.
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
   - `services/kopis.py` `fetch_venues(signgucode)` — 공연시설. ✅ 키 갱신 후 작동, **signgucode=sgg_code[:4] server-side 정확 필터**(2026-06-29 검증).
   - ✅ **엔드포인트 배선 완료** (2026-06-29): 5키 전부 `POST /seed` 의 context 에 배선(아래 7번). ✅ **SEOUL 행정동코드 자동화** (2026-06-29): 좌표→`kakao.coord_to_hcode`(coord2regioncode H코드)→`[:8]`=서울 ADSTRD_CODE_SE. `seoul.fetch_living_population(lat,lon)` 자동 해석. ✅ KOPIS signgucode 매핑 완료. ⬜ 잔여: matrix `source_type` 통합(모드A 편입은 선택).
5. ~~SBIZ365 #29·#30 재분류~~ → ✅ **완료** (2026-06-29). 판정: SBIZ365는 REST API 없음(`SBIZ365_KEY`=포털용, fetch 불가). **결정**:
   - 점포 '분포'(업종별 점포수)는 작동하는 실API **B553077 상가(상권)정보**를 `services/sangwon.py`로 정식 승격(데모→서비스). `fetch_store_district(lat,lon,radius)` = 반경 내 점포수+업종 대분류 집계. 여의도 500m 2,275개 검증. 라이브 테스트 1건. §2 차별점 통과(실API·코드계산·출처).
   - 매출/폐업/창업률·빈상가(#29b·#30)는 fileData CSV 적재만 가능 → **현재 제외**(§2 실시간 API 우선·bus-factor). 필요시 후속 CSV 적재 설계. API_MASTER_LIST.md 갱신.
   - ✅ 엔드포인트 배선: `sangwon.py` → `POST /seed` context.stores (7번). ⬜ 잔여: 수급진단 업종분석 편입(선택).
6. ~~INTEGRATION.md P12 연결 준비~~ → ✅ **완료** (2026-06-29). 3종 준비물:
   - `services/http_retry.py` `request_with_retry` — 5xx·네트워크만 재시도(지수백오프), 4xx 즉시. 단위테스트 5건(MockTransport). ✅ **기존 외부호출 전반 적용 완료** (2026-06-29): kakao·resolve·juso·kosis·vworld·molit·airkorea·sangwon·rone·neis·seoul·kopis·kma 의 GET 22곳. tiles(타일별 회색채움 설계)·osm(Overpass rate-limit)은 의도적 제외.
   - `schemas/project_seed.py` `Site`/`ProjectSeed` — 세 앱 공유 계약(INTEGRATION §4). site=공유 식별자(좌표·bcode·sgg·pnu), context=터읽기, law/knowledge=형제앱(느슨 dict, 경계).
   - `services/site_seed.py` `build_site`/`build_project_seed` — 주소 해석 단일진입점(resolve 1곳 + VWorld pnu 보강). 라이브테스트 3건.
7. ✅ **신규 서비스 7종 엔드포인트 배선 완료** (2026-06-29). `POST /seed`(`routers/seed.py`) = 보드 합본 진입점. `build_site`(site_seed)로 공유 site + `context`에 6개 데이터 서비스 best-effort 배선: stores(sangwon)·schools(neis)·real_estate_index(rone)·weather(kma, timeout 12s)·living_population(seoul, adstrd_code 지정 시)·venues(kopis). 각 graceful(None+notes). 출력=`ProjectSeed`(law·knowledge는 형제앱 자리). §5 표 등재, 라이브 테스트 2건. 검증: 여의대로24 1km → 상권5922·학교47·지수89.9·날씨29℃·생활인구191469·공연None(키대기). 버그수정: resolve sido가 카카오 축약형("서울")이라 NEIS `_OFC_CODE`에 축약형 추가.
   - ✅ http_retry 전반 적용·SEOUL 행정동코드 자동화·`verify_apis.py` 갱신 완료(2026-06-29). `verify_apis.py`: 건축HUB 표제부·VWorld 개별공시지가 프로브 추가, 아파트매매 `resultCode=000` 정상인식. 실행결과 WORKS=15. ✅ 죽은 `molit.fetch_land_price` 제거 완료(코드리뷰).
   - ✅ **KOPIS signgucode 연결 완료** (2026-06-29, 키 갱신 후). 실API 검증: **signgucode = 행안부 시군구코드 앞 4자리**(영등포 11560→1156, 관악 1162·부산해운대 2635·성남분당 4113 server-side 정확). `fetch_venues(signgucode=sgg_code[:4])` 서버측 필터 — 이전 이름필터는 전국 1000건 상한에 잘려 영등포 12건만(실제 61건) 누락. **효율 아니라 정확성 수정**. rows 상한 100(rc06).
   - ✅ **/seed 병렬화 + seoul 최신일 캐시** (2026-06-29). seed.py 8블록 순차→ThreadPoolExecutor. seoul `_latest_date`(서울서버 ~3s 단독 병목, 하루1회·행정동무관)를 `date.today()` 키로 캐시. 복합 효과: 순차~8s→병렬3.5s→warm 0.65s. 스레드안전(서비스별 자체 client·distinct 캐시키).
   - ✅ **프론트 노출 완료** (2026-06-29): F탭(/site)·G탭(/seed) + C탭(수급진단)에 정원·전국대비밀도 노출. 문화시설 수급규칙(6번째) 추가.
8. ✅ **어린이집·문화시설·수급진단 규칙 확장 완료** (2026-06-29). `services/childcare.py`(cpmsapi021, XML, 정원·개수)·`services/culture.py`(B553457 10종, pblshYr 자동탐지, by_type) 신설 → `/seed` context.childcare·context.culture 배선. 수급진단에 어린이집 **정원** 편입(`capacity_source:"childcare"`, `SupplySignal.capacity`). `supply_demand.json`에 **의료시설 수급**(고령인구비율×병원·의원·약국)·**초등학교 수급**(유소년인구비율×초등학교) 추가 → 총 5개 규칙. 문화시설은 수요 proxy 없어 수급진단 미편입·현황만. 전체 테스트 101 통과. *(이후 2026-06-30: 문화시설 수급 추가 — 생산가능인구비율을 proxy로 → 총 6개 규칙)*
9. ✅ **TMAP 보행자 등시선 배선 완료** (2026-06-29). SK OpenAPI 앱 활성화 확인 후 `services/tmap.py` 신설. 구현: 16방향 × 3시간대(5·10·15분) = 48 TMAP 보행자 경로 병렬 호출(`ThreadPoolExecutor max_workers=8`, 실측 ~0.8s) → 경로 시간 기준 절삭(`_trim_route_at_time`) → 경계점 연결해 등시선 폴리곤 생성. `compose_map()`에 `isochrone` 파라미터 추가 — PIL `draw.polygon`으로 5·10·15분 채움 폴리곤(외→내 순). `/facilities/map` 요청에 `isochrone: true`(기본값) 추가. graceful — TMAP 실패 시 기존 반경원으로 폴백. 반경원이 "카카오 최대반경 2km 기계적 원"인 반면 등시선은 실도보 가능권 표시 — 언덕·도로·막힌 골목 반영.
10. ✅ **수급진단 반경 비례 정규화 + 전국 밀도 벤치마크 완료** (2026-06-29). `_supply_level`→`_supply_level_count(count, low_max, high_min, radius)`: 임계값을 `(radius/1000)²`으로 스케일(반경 2km → 면적 4배 → 임계값 4배). `supply_demand.json`에 규칙별 `national_density_per_10k`·`national_density_source`·`density_low_pct`·`density_high_pct` 추가(보육 7.7·노인 13.0·1인가구 14.5·의료 12.1·초등 1.2, 각 보건복지부/교육부/HIRA 2024 출처). `SupplySignal`에 `density_per_10k`·`national_density_per_10k`·`vs_national_pct` 필드 추가(참고용 — 분모가 시군구 전체인구라 primary 판정엔 미사용, note에 텍스트로 병기). `stats.fetch_total_pop(sgg_code)` 추가 — KOSIS DT_1B04005N 캐시 재사용, 추가 API 호출 없음. 테스트 6/6 통과.

### 9.2 확인할 것 (사용자 포털 액션 — 풀려야 코드가 의미 생김)

- [ ] **data.go.kr 활용신청**: 에어코리아 `B552584`(신청완료·대기) · 건축물대장 `BldRgstService_v2` · 아파트매매 `RTMSDataSvcAptTradeDev`(신청완료·대기) · 문화기반시설총람 `B553457`(신청완료). → 승인 후 `scripts/verify_apis.py` 재실행으로 전파 확인(403/500→00).
  - ~~표준지공시지가~~ → **불필요**: VWorld 개별공시지가로 우회 완료(§9.1-1).
  - 경로당(15114136) → **VWorld 검색 API로 우회 완료**(§8.5). 어린이집 → ✅ **정보공개포털 cpmsapi021 연결 완료**(2026-06-29, `CHILDCARE_INFO_KEY`, `services/childcare.py`→`/seed`. 영등포 50개·정원2785 검증). data.go.kr 경로는 불필요.
  - 문화기반시설총람 `B553457` → ✅ **연결 완료**(2026-06-29, `services/culture.py`→`/seed` context.culture). `DATA_GO_KR_API_KEY`+`pblshYr`(발간연도 자동탐지, 최신2024)+`sggCd`, 10개 시설유형 operation(박물관·미술관·문예회관·국립/공공도서관·생활문화센터·지방문화원·문화의집·지역문화재단·문학관). 종로73·강남31·부산중구7 등 전국 검증. ⚠️ kcisa `CULTURE_KEY`는 401 — data.go.kr 경로가 정답.
  - **KOPIS** → ✅ 키 갱신 후 인증 통과(이전 02). **어린이집 상세** cpmsapi030(`CHILDCARE_DETAIL_KEY`, 위경도·CCTV·연령별정원)은 arcode 체계 별도 — 필요 시 추가.
- ✅ **TMAP #103 완료** (2026-06-29): SK OpenAPI 앱 활성화 + Pedestrian Route API 구독. `services/tmap.py` 등시선 배선 완료(§9.1 항목 9).
- [ ] **LIBRARY #122**: data4library 계정 OpenAPI 활성화 승인 (현재 "API 미활성").
- [ ] **CULTURE #134 경로 택1**: data.go.kr `B553457` 활용신청 **또는** kcisa 구독 데이터셋의 정확한 `API_CCA` 번호 확인.
- [ ] **JUSO 운영키 (DEFERRED D2)**: 배포 전 dev키→운영키 교체.
- ✅ **KOPIS 키 갱신 완료** (2026-06-29): 사용자 재등록 후 인증 통과. `/seed` context.venues 작동.
- [ ] **EUM 진행 여부 결정 (DEFERRED D6)**: 규제=arch-law-diagnose 담당 — 가져올지/말지 제품 결정.

### 9.3 하면 좋은 것 (개선·기술부채)

- **`verify_apis.py` 주기 점검 자산화** — CI/cron 으로 키 만료·승인 전파 자동 감지. ✅ 2026-06-29 현황 반영(건축HUB·VWorld 공시지가 프로브 추가, 아파트매매 000 인식, KOPIS 02 분류). 실행 WORKS=16(TMAP 추가). ⚠️ VWorld 개발키 **2026-12-26 만료**(INTEGRATION.md §5) 추적.
- **테스트 보강** — `/site` 무테스트. → ✅ 해소(test_site_live·test_seed_live·신규서비스 live 추가).
- **KOSIS 미확정 지표 확정 (DEFERRED D4, §8.6)** — 인구밀도·사업체수·주택보급률 등. 면적/인구 결합은 P11 수급진단에서 함께.
- **matrix.json / implications.json 건축가 검수 (DEFERRED D5)** — 항목·우선순위·함의 규칙 실설계 관점 보강(코드 수정 없이 JSON만).
- **인프라 부채** — StarletteDeprecation httpx 경고(D7), GCS 캐시+TTL(D8), 합성 PNG 다중인스턴스(D10).
- ✅ **/site 병렬화 완료** (2026-06-30) — 4블록+실거래4종+건축물대장 2콜 ThreadPoolExecutor. 순차합 ~14.5s→~3s. 병목=건축HUB 건축물대장 내부 2콜(병렬로 해소). 잔여: /site·/seed SGIS 토큰 공유 최적화(현재 블록별 auth 중복 가능, 캐시로 대부분 흡수).
