# SPEC.md — 터읽기 (arch-site-context) 역추론 명세

> 이 문서는 코드베이스를 읽고 목적·로직·구조·한계를 역추론한 명세다.
> 불확실한 부분은 **[추정]** 으로 표시한다.
> 최종 판단 권위는 CLAUDE.md 및 실제 코드다.

---

## 1. 목적

**주소 한 줄 → 건축 대지 주변 맥락 보고서 자동 생성.**

건축가가 설계 착수 전 반나절 이상 걸리던 '대지 주변 인문·생활 조사'를, 실제 공공 API에서 끌어온 수치로 자동화한다. 최종 설계 판단은 사람이 한다.

### 사용자 페르소나 [추정]

- **1차 사용자**: 공모(설계경기)·실무 설계를 준비하는 건축가
- **목적 맥락**: 대지분석 보드의 '인문·생활' 파트를 채우는 용도
- **보완 도구**: 일조·바람·사업수지·규제 해석 도구와 병행 사용 (이 앱은 그쪽을 만들지 않음)

---

## 2. 핵심 설계 원칙 7가지

이 원칙들은 단순 가이드라인이 아니라 **코드 전체에 구조적으로 박혀 있다.**

| # | 원칙 | 코드 표현 |
|---|------|---------|
| 1 | **실제 API에서만** — AI 기억·추정 금지 | KOSIS·카카오·에어코리아 등 직접 호출. 값 없으면 `None`, 추정 없음 |
| 2 | **수치는 코드, 표현만 AI** | `facts[]`·`implications[]`은 규칙·KOSIS가 만든다. Claude는 `draft_paragraph` 서술만 |
| 3 | **확인 불가 하드블록** | 데이터 없으면 `ErrorBlock` 반환 or `notes` 기록, 빈 추정값 생성 금지 |
| 4 | **출처·기준 명시** | 모든 `Fact`에 `source_tbl`, `year` 필드. "○○구 기준" 문단 필수 |
| 5 | **판단은 분리·라벨하되 최종 결정은 사람** | 사실/AI의견을 벽 분리(종합 산출 `synthesis` ①사실 ②AI판단). 모든 `Implication`·`Diagnosis`·드라이버·POR가 `tag:"참고"`. **종합점수·순위 없음** |
| 6 | **모델은 Claude 하나** | 다벤더·교차검증 금지. Claude 계열 내 티어 분리 허용: `synthesis.py` ①`claude-sonnet-5`·②`claude-opus-4-8`, `narrative.py`·`ask.py`는 Opus |
| 7 | **설정은 JSON** | `matrix`·`implications`·`supply_demand`·`cross_context`·`driver_rules`·`archetype_rules`·`program_rules`.json — 코드 수정 없이 건축가가 편집 |

> **S/T 시리즈 (종합 읽기·2026-07-09):** 위 원칙 위에서 흩어진 출력을 `/board` 로 합성 + 해석 레이어를 얹었다.
> **S1** 데이터 근접도 등급 · **S2** 교차규칙 엔진 · **S3** `/board` 통합 진입점 · **S4** 종합 산출(사실/AI의견 벽 분리) ·
> **T1** 정규화 지수(전국=100)+근거 드릴다운 · **T1.5** 대지 아키타입 · **T2** 설계 드라이버 · **T3** 프로그램 함의(POR) · **T4** 보드 내보내기 · **T5** 방법론·데이터 부록(출처·산정식·한계 자동 각인, 공모·감사 대비).
> 전부 LLM 0(S4 표현만)·새 숫자 0. 상세: CLAUDE.md §8.11·§8.12.
>
> **arch-site-model 결합 (2026-07-09):** 형제앱(주소→물리 3D 지형/건물)의 출력을 `POST /board {model:...}` 로 주입하면 물리+인문 = 완전한 보드. **터읽기는 provider — 형제를 호출하지 않고**(competition과 동일 경계) 넘겨받은 모델을 `summarize_model`로 요약 + `board_view` 축측 매싱으로 렌더만. `ProjectSeed.model` 슬롯(law·knowledge 대칭). 상세: CLAUDE.md §8.12·INTEGRATION.md §4.

---

## 3. 전체 구조

```
arch-site-context/
├── app/
│   ├── main.py                  # FastAPI 진입점 (라우터 등록, 정적 서빙)
│   ├── routers/                 # 엔드포인트 (오케스트레이션만, 비즈니스 로직 없음)
│   │   ├── analyze.py           # POST /analyze   (모드 A)
│   │   ├── facilities.py        # POST /facilities, /facilities/map (모드 B)
│   │   ├── diagnose.py          # POST /diagnose  (P11 수급진단)
│   │   ├── compare.py           # POST /compare   (P9 후보지 비교)
│   │   ├── ask.py               # POST /ask       (P10 물어보기)
│   │   ├── site.py              # POST /site      (P14 대지 기본정보)
│   │   ├── seed.py              # POST /seed      (P14 보드 합본, ThreadPoolExecutor 병렬)
│   │   ├── readout.py           # POST /readout   (공동주택 대지 readout)
│   │   ├── board.py             # POST /board, /board/view (S/T 종합 읽기 + 보드 렌더)
│   │   ├── matrix.py            # GET  /matrix    (투명성)
│   │   └── health.py            # GET  /health
│   ├── services/
│   │   ├── resolve.py           # 주소 → 좌표·법정동코드 (카카오+JUSO)
│   │   ├── kosis.py             # KOSIS OpenAPI 호출 + 캐시
│   │   ├── airkorea.py          # 에어코리아 대기질
│   │   ├── kakao.py             # 카카오 로컬 검색 (적응 분할)
│   │   ├── vworld.py            # VWorld: 위성타일·시설검색·공시지가
│   │   ├── molit.py             # 실거래(RTMS)·건축물대장(건축HUB)
│   │   ├── facilities.py        # 모드 B 오케스트레이션 (카카오+OSM+VWorld 병합)
│   │   ├── stats.py             # 통계 조립 (KOSIS + 에어코리아 → facts[])
│   │   ├── matrix.py            # matrix.json 로더
│   │   ├── implications.py      # implications.json 룩업
│   │   ├── narrative.py         # Claude 한 문단 서술 + 규칙 폴백
│   │   ├── diagnose.py          # P11 수급진단 오케스트레이션
│   │   ├── compare.py           # P9 후보지 비교 번들
│   │   ├── ask.py               # P10 그라운디드 답변 + 웹검색 폴백
│   │   ├── sgis.py              # SGIS 반경 집계구 실인구 · 재해위험(홍수·산사태·폭염)
│   │   ├── cross_context.py     # S2 도메인 횡단 교차 시사점 엔진 (규칙, LLM 0)
│   │   ├── design_drivers.py    # T2 설계 드라이버 랭킹 (증거강도)
│   │   ├── archetype.py         # T1.5 대지 아키타입 분류 (규칙 룩업)
│   │   ├── program.py           # T3 프로그램 함의(POR) — 카테고리별 (cross_context 절 재사용)
│   │   ├── synthesis.py         # S4 종합 산출 ①사실(Sonnet) ②AI판단(Opus)
│   │   ├── methodology.py       # T5 방법론·데이터 부록 (출처·산정식·한계, LLM 0)
│   │   ├── site_model.py        # arch-site-model 물리 3D 결합 (넘겨받은 모델 요약·렌더)
│   │   ├── board_contract.py    # /board 공유 계약 (board_brief·board_to_project_seed)
│   │   ├── board_view.py        # T4 대지분석 보드 자체완결 HTML 렌더 (+물리모델 축측 매싱)
│   │   ├── map_compose.py       # PIL 위성 PNG 합성
│   │   ├── tmap.py              # TMAP 보행자 경로 → 등시선 폴리곤
│   │   ├── tiles.py             # VWorld 타일 조합 + 좌표↔픽셀 변환
│   │   ├── geo.py               # 하버사인 거리, 반경 밴드, bbox
│   │   ├── cache.py             # FileCache/MemoryCache/GCSCache 추상화
│   │   ├── http_retry.py        # 지수 백오프 재시도 (5xx·네트워크만)
│   │   ├── site_seed.py         # 주소 단일 해석 진입점 → Site 공유
│   │   ├── juso.py              # 행안부 도로명주소 정규화
│   │   ├── sangwon.py           # 상권(상가)정보
│   │   ├── neis.py              # 학교 (시도교육청)
│   │   ├── childcare.py         # 어린이집 개수·정원 (정보공개포털)
│   │   ├── culture.py           # 문화기반시설총람 10종
│   │   ├── rone.py              # 부동산원 가격지수
│   │   ├── kma.py               # 기상청 단기예보
│   │   ├── seoul.py             # 서울 생활인구 (서울시 전용)
│   │   └── kopis.py             # 공연시설
│   ├── schemas/                 # Pydantic v2 데이터 계약 (§5)
│   └── data/                    # 외부 JSON 설정 (§6)
│       ├── matrix.json          # 용도별 KOSIS 지표 목록
│       ├── implications.json    # 단일 지표 함의 규칙
│       ├── supply_demand.json   # 수급진단 규칙·임계값
│       ├── cross_context.json   # S2 교차 시사점 규칙
│       ├── driver_rules.json    # T2 설계 드라이버 규칙·가중치
│       ├── archetype_rules.json # T1.5 대지 아키타입 규칙
│       ├── program_rules.json   # T3 프로그램 함의(POR) 규칙
│       └── methodology.json     # T5 방법론 부록 출처 카탈로그·산정식
├── mcp_server/                  # 터읽기 MCP 서버 (read_site_context·diagnose_supply)
├── frontend/                    # React + Vite + Tailwind
│   └── src/
│       ├── App.jsx              # 탭 라우팅 (A~I)
│       ├── TabA.jsx ~ TabI.jsx  # A 지역통계·B 시설·C 수급·D 비교·E 물어보기·F 대지정보·G 보드합본·H readout·I 종합읽기(/board)
│       ├── api.js               # fetch 헬퍼
│       └── ui.jsx               # 공통 UI (IndexBar·ProximityChip 등)
└── tests/                       # pytest (순수 로직 + live skipif)
```

---

## 4. 엔드포인트 명세

### 4.1 POST /analyze — 지역 통계 (모드 A)

**입력:**
```json
{ "address": "서울특별시 영등포구 여의대로 24", "use_type": "주거", "year": null }
```

**처리 흐름:**
```
resolve_address(address)
  → sgg_code 없으면 ErrorBlock(NO_REGION_CODE)
  → collect_facts(sgg_code, use_type)   // KOSIS + 에어코리아
  → collect_common_facts(sido, sigungu) // _common 항목 (에어코리아 등)
  → derive_implications(facts, use_type) // implications.json 룩업
  → compose_narrative(facts, implications) // Claude 1회 or 규칙 폴백
```

**출력 (RegionStat):**
```json
{
  "region": { "name": "영등포구", "code": "11560", "resolution": "시군구" },
  "year": 2024, "use_type": "주거",
  "facts": [
    { "item": "1인가구비율", "value": 38.2, "national_avg": 33.4,
      "unit": "%", "source_tbl": "DT_1JC1511", "year": 2024 }
  ],
  "implications": [
    { "text": "소형 평형·공유공간 검토", "basis": "1인가구비율", "tag": "참고" }
  ],
  "draft_paragraph": "영등포구는 1인가구 비율이 전국 평균보다 높아...",
  "source": "ai",
  "notes": []
}
```

**ErrorBlock 조건:** ADDR_UNRESOLVED · NO_REGION_CODE · NO_DATA

---

### 4.2 POST /facilities — 주변 시설 (모드 B)

**입력:**
```json
{ "address": "...", "kinds": ["어린이집", "경로당"], "radii": [500, 1000, 2000] }
```

**처리 흐름:**
```
resolve_address(address)
  → 카카오 키워드 검색 (적응 분할, 45건 상한 회피)
  → OSM Overpass 보완 (공공시설)
  → VWorld 검색 보완 (비상업 시설 — 경로당·노인복지관 등)
  → 중복 제거 (이름+좌표 6자리)
  → 하버사인 거리 계산 + 반경 밴드 분류
  → 정렬 (거리순)
```

**counts 누적 방식:** 500m 건물은 500/1000/2000 밴드 전부 집계 (누적 포함).

**출력 (FacilityResult):**
```json
{
  "center": { "lat": 37.52, "lon": 126.92, "address": "..." },
  "results": [
    { "kind": "경로당", "name": "여의도경로당", "lat": 37.52, "lon": 126.91,
      "dist_m": 320, "radius_band": "500", "src": "vworld" }
  ],
  "counts": {
    "500": { "어린이집": 3, "경로당": 12 },
    "1000": { "어린이집": 8, "경로당": 35 }
  },
  "source": "kakao+osm+vworld",
  "base_date": "2026-06-29",
  "notes": []
}
```

---

### 4.3 POST /facilities/map — 위성 PNG 합성 (모드 B)

**추가 입력 필드:**
```json
{ "basemap": "vworld", "isochrone": true }
```

**처리 흐름:**
```
build_facility_result(...)          // 시설 검색
  → tmap.compute_isochrone(...)     // TMAP 보행자 등시선 (isochrone=true 시)
  → compose_map(result, isochrone)  // PIL PNG 합성
  → 파일 저장 → URL 반환
```

**출력:**
```json
{
  "url": "/files/maps/map_abc123.png",
  "center": { ... }, "counts": { ... },
  "basemap": "vworld", "source": "kakao+vworld+tmap",
  "base_date": "...", "notes": []
}
```

**등시선 생성 알고리즘:**
1. 16방향 × 3시간(5·10·15분) = 48회 TMAP 보행자 경로 병렬 호출 (`ThreadPoolExecutor`)
2. 각 경로에서 목표 시간(초) 도달 지점 보간 → 꼭짓점
3. 꼭짓점 연결 → 폴리곤 → PIL 채움
4. 실패 방향 제외 (graceful), 전부 실패 시 반경원으로 폴백

---

### 4.4 POST /diagnose — 수급진단 (P11 ★간판)

**입력:**
```json
{ "address": "...", "radius": 1000 }
```

**처리 흐름:**
```
resolve_address(address)
  → collect_facts_by_items(sgg_code, [수요지표 distinct])   // KOSIS
  → build_facility_result(address, [공급 종류 all])        // 카카오+VWorld
  → _collect_capacity(rules)                               // 어린이집 정원 (cpmsapi021)
  → fetch_total_pop(sgg_code)                              // 시군구 총인구 (밀도용)
  → cross_rules(facts, band, capacity, total_pop)          // 순수 교차 로직
```

**판정 로직:**
```
수요 레벨:
  value > national_avg + margin  → "높음"
  value < national_avg - margin  → "낮음"
  그 사이                        → "평이"
  national_avg 없음              → "불명"

공급 레벨 (반경 비례, primary):
  scale = (radius / 1000)²
  count ≤ supply_low_max × scale  → "적음"
  count ≥ supply_high_min × scale → "많음"
  그 사이                          → "보통"

공급 밀도 (보조 참고):
  density_per_10k = count / (시군구총인구 / 10_000)
  vs_national_pct = density_per_10k / national_density_per_10k × 100
  → SupplySignal 필드로 제공, 판정에는 미사용
```

**출력 (DiagnoseResult):**
```json
{
  "region": { "name": "영등포구", "code": "11560", "resolution": "시군구" },
  "radius": 1000,
  "diagnoses": [
    {
      "name": "보육시설 수급",
      "demand": { "item": "유소년인구비율", "value": 8.3, "national_avg": 10.3, "level": "낮음" },
      "supply": {
        "kinds": ["어린이집", "유치원"], "count": 23, "radius": 1000, "level": "많음",
        "density_per_10k": 0.62, "national_density_per_10k": 7.7, "vs_national_pct": 8,
        "capacity": 2785, "capacity_scope": "영등포구"
      },
      "signal": "수요 낮음·공급 많음",
      "note": "유소년인구비율 8.3%(전국 10.3%) · 반경 1000m 어린이집·유치원 23개 → 과잉 여부 점검",
      "tag": "참고"
    }
  ],
  "source": "kakao+kosis",
  "base_date": "2026-06-29",
  "notes": []
}
```

---

### 4.5 POST /compare — 후보지 비교 (P9)

**입력:**
```json
{ "addresses": ["주소A", "주소B"], "use_type": "주거", "radius": 1000, "kinds": [] }
```

**특징:**
- 2~5개 주소 제한
- 후보지별 격리 실패: 한 주소 오류 → `CompareSite.error` 기록, 나머지 계속
- 종합점수 없음 — 컬럼 정렬만 (판단은 사람, 원칙 5)
- 수요지표 1세트 + 시설 검색 1세트만 호출 (지역코드가 같으면 KOSIS 캐시 재사용)

---

### 4.6 POST /ask — 물어보기 (P10)

**입력:**
```json
{ "address": "...", "question": "이 지역 어린이집이 부족한가요?", "web": false }
```

**처리 흐름:**
```
gather_bundle(address) → facts + counts + diagnoses  // A·B·P11 한 번에
  → answer_grounded(bundle, question)  // Claude: 데이터 위에서만 답
      answerable=false 시: "확인 불가:" 시작
  → (web=true) answer_web(question)    // Claude web_search 서버툴 폴백
      최대 4회 루프, web_sources[] 반환
```

**출력 `source` 값:**
- `"ai"` — 데이터 기반 그라운디드 답변
- `"ai_web"` — 웹검색 폴백 사용
- `"no_data"` — 번들 없음
- `"ai_unavailable"` — Claude API 오류

---

### 4.7 POST /site — 대지 기본정보 (P14)

**입력:** `{ "address": "..." }`

**수집 항목:**
| 항목 | API | 비고 |
|------|-----|------|
| 개별공시지가 | VWorld LP_PA_CBND_BUBUN | 필지별(PNU 기반), data.go.kr 미승인으로 우회 |
| 실거래가 | 국토부 RTMS 4종 | 토지매매·아파트매매·연립다세대·아파트전월세 |
| 건축물대장 | 건축HUB BldRgstHubService | 표제부+총괄표제부 (건폐율·용적률) |

**각 API 독립 실패 격리** — 하나 오류여도 부분 반환.

---

### 4.8 POST /seed — 보드 합본 (P14)

**입력:** `{ "address": "...", "radius": 1000, "adstrd_code": null }`

**출력 (ProjectSeed) 구조:**
```json
{
  "site": { "address", "lat", "lon", "pnu", "bcode", "sgg_code", "sido", "sigungu", "eupmyeondong" },
  "context": {
    "stores": { ... },            // 상권 (data.go.kr B553077)
    "schools": { ... },           // 학교 (NEIS)
    "childcare": { ... },         // 어린이집 (cpmsapi021)
    "culture": { ... },           // 문화시설 10종 (B553457)
    "real_estate_index": { ... }, // 부동산지수 (R-ONE)
    "weather": { ... },           // 날씨 (기상청)
    "living_population": { ... }, // 생활인구 (서울 전용)
    "venues": { ... },            // 공연시설 (KOPIS)
    "notes": []
  },
  "law": null,       // 형제앱 arch-law-diagnose 주입 자리
  "knowledge": null, // 형제앱 arch-law-graph 주입 자리
  "base_date": "..."
}
```

**병렬 수집:** 8개 context 블록을 `ThreadPoolExecutor`로 동시 호출(서비스별 자체 client + 소스별 distinct 캐시키 → 스레드 안전). 콜드 합계 ~8s → 가장 느린 블록 시간으로 단축. 생활인구(seoul)는 최신 가용일을 `date.today()` 키로 캐시 — warm 호출 시 재탐지 생략.

---

### 4.9 POST /readout — 공동주택 대지 readout

**입력:** `{ "address": "...", "use_type": "주거", "project_type": "재건축" }`
- `project_type`: 재건축·재개발·민간·주상복합 (강조 프리셋만 다름, 데이터는 동일)

**처리 흐름:**
```
resolve_address(address)
  → collect_facts(sgg_code, use_type)              // ① 기존 matrix 지표(인구·가구)
  → census_multidim.fetch_census_indicator(...) ×4 // ② 크랙 census 지표
  → 파생(사업체밀도·장애인비율·신혼부부/세대)         // ③ 정규화
  → 유형 프리셋 강조(emphasized) 부여
```

**② 크랙 census 지표 (다차원 표 — `census_multidim`):**
다차원 KOSIS 표(시군구×산업×규모 등)는 표마다 지역코드체계·분류차원이 달라 범용질의가 err21.
해결: `getMeta type=ITM` 응답이 OBJ_NM 으로 모든 차원을 담음 → 지역차원에서 시군구코드(이름매칭) +
분류차원의 '전체/계' 합계코드를 뽑아 질의 구성. 전국 작동(census 코드 자동 해석).
- 사업체수(DT_1BD1032, +산업대분류 구성) · 빈집(DT_1JU1512) · 신혼부부(DT_1NW1037) · 등록장애인(DT_11761_N009)

**출력 (ReadoutResult):** `site` · `project_type` · `demographics[]`(matrix 지표) · `context[]`(census 지표, 일부 breakdown) · `derived[]`(파생) · `notes[]`(시군구 캐비엇·greenfield 경고). 각 지표 graceful.

### 4.10 POST /board — 종합 읽기 (S/T 시리즈) ★

**입력:** `{ address, use_type, radius=1000, resolution="시군구", synthesize=false, brief=false, model=null }`
- `model`: arch-site-model 물리 3D 출력(assembler 가 넘김 — 터읽기는 호출 안 함). 있으면 요약 + 매싱 미리보기.

**처리 흐름 (오케스트레이션만·재계산 0):**
```
build_site(address)  // 주소 1회 fail-fast (공유 Site·PNU)
  → 4 도메인 브랜치 병렬 (ThreadPoolExecutor):
       analyze() → facts(지수·근접도)+implications+region
       build_diagnosis() → diagnoses(수급)
       site_info() → hazards·공시지가·건축물대장·실거래
       seed() → context(상권·학교·문화·날씨…)
  → derive_cross_context()  // S2 교차 시사점
  → derive_design_drivers()  // T2 지배 드라이버 2~3개
  → classify_archetype()     // T1.5 동네 유형
  → derive_program()         // T3 프로그램 함의(POR)
  → build_methodology()      // T5 출처·산정식·한계 부록 (조인만, LLM 0)
  → (model 넘어오면) summarize_model()  // arch-site-model 물리 3D 압축 요약
  → (synthesize=true) synthesize()  // S4 ①사실(Sonnet) ②AI판단(Opus)
  → coverage(도메인 확보 여부, no silent skip)
```

**출력 (BoardResult, `schema_version:"board/1.0"`):** `site` · `region` · `archetype` · `facts[]`(index·proximity) · `implications[]` · `diagnoses[]` · `design_drivers[]` · `program_implications[]` · `hazards` · `land_price`·`building`·`real_estate` · `context` · `cross_implications[]` · `coverage[]` · `methodology`(T5 출처·산정식·한계) · `model`(arch-site-model 물리 3D 요약, `model` 입력 시) · `synthesis`(opt-in) · `notes[]`.

- **`brief=true`** → `board_brief`(압축 투영, ~66KB→~7KB, 원시 seed context 제외·해석층만). 제안서·MCP·형제앱 주입용.
- 종합점수·순위 없음 (원칙 5). 각 브랜치 graceful — 실패 격리.

### 4.11 POST /board/view — 대지분석 보드 렌더 (T4)

/board 빌드 → `board_view.render_board_html`(자체완결 HTML: 지도 앵커·물리모델 축측 매싱·아키타입·드라이버·POR·종합·지수·방법론 부록) → `out/boards/*.html` 저장 → `{ url: "/files/boards/…", has_map }` 반환. 인쇄 시 PDF. `_satellite_anchor`가 VWorld 위성+반경링 data URI 임베드, `model` 넘어오면 `_massing_anchor`가 건물 footprint를 축측(2:1 이소) 투영해 매싱 미리보기 임베드 — **three.js 없이 서버사이드 PIL**로 자체완결·오프라인 유지 (둘 다 graceful).

**MCP (`mcp_server/server.py`, FastMCP):** `read_site_context`(→board_brief) · `diagnose_supply`(→수급진단). 기존 서비스 얇게 래핑 — 개별·에이전트 파이프라인 둘 다.

---

## 5. 데이터 계약 요약

### 5.1 공통 패턴

- **`Fact`**: `{ item, value, national_avg, unit, source_tbl, year, scope, scope_level }` + 파생 `proximity`(S1: 대지>반경>읍면동>시군구>proxy), `index`(T1: 전국=100=value/national×100, 비율 지표만), `index_band`(상회|비슷|하회). 수치와 출처 분리 불가
- **`Implication`**: 항상 `{ text, basis, tag:"참고" }` — '좋다/나쁘다' 단정 없음
- **`ErrorBlock`**: `{ code, message }` + HTTP 422 — 추정·빈 값 반환 없음
- **`notes[]`**: 모든 응답에 포함 — 실패·우회·주의 사항 정직 기록

### 5.1b S/T 시리즈 스키마 (해석 레이어)

- **`Proximity`**(schemas/proximity): 근접도 등급 Literal + `proximity_of(scope_level)`·`proximity_rank`. 순수 메타데이터.
- **`CrossImplication`**(S2): `{ name, text, basis[{key,detail,proximity}], domains, tag }` — 도메인 횡단 시사점.
- **`DesignDriver`**(T2): `{ rank, name, response, strength, evidence[], tag }` — 증거강도 랭킹.
- **`Archetype`**(T1.5): `{ name, group, description, match_score, evidence[], alternatives[], tag }` — 동네 유형.
- **`ProgramItem`**(T3): `{ category, recommendation, basis[], tag }` — 카테고리별 POR 권고.
- **`Synthesis`**(S4): `{ interpretation, interpretation_source/model, judgment, judgment_source/model, judgment_label }` — 사실/AI의견 벽 분리.
- **`Methodology`**(T5): `{ summary, resolution, sources[{key,name,publisher,api,kind,used_for,years,proximity}], formulas[{item,formula,note}], limitations[] }` — 이 보드에 실제로 기여한 출처·산정식·한계 자동 각인(기여한 것만·미등록은 원시 키+note, LLM 0).
- **`SiteModelSummary`**(arch-site-model 결합): `{ source, building_count, solids, cadastral_parcels, elev_range_m, origin_offset, radius_m, footprints[], heights_m[], files, provenance }` — 넘겨받은 물리 3D의 압축 요약(원시 terrain 미보관, footprints≤400).
- **`BoardResult`**(S3, `board/1.0`) / **`board_brief`**(`board_brief/1.0`) / **`Site`·`ProjectSeed`**(`project_seed/1.0`, 형제앱 공유 계약 — `law`·`knowledge`·`model` 슬롯, 각 앱이 스키마 주인).

### 5.2 SupplySignal 필드 (P11 확장 후)

```python
class SupplySignal:
    kinds: List[str]
    count: int          # 반경 내 실제 개수 (primary 판정)
    radius: int
    level: str          # "적음"|"보통"|"많음" (count 기반)
    density_per_10k: Optional[float]          # count/(시군구총인구/10000) (참고)
    national_density_per_10k: Optional[float] # 전국 만명당 기준값 (참고)
    vs_national_pct: Optional[int]            # 전국 대비 % (참고)
    capacity: Optional[int]                   # 시군구 어린이집 정원 (반경 개수와 단위 다름)
    capacity_scope: Optional[str]
```

### 5.3 ResolvedAddress (내부 전달 객체)

```python
@dataclass
class ResolvedAddress:
    lat: float
    lon: float
    address: str
    bcode: str       # 법정동 10자리
    sgg_code: str    # 앞 5자리 (시군구, 모드 A/C 기준)
    sido: str
    sigungu: str
    eupmyeondong: str
    notes: List[str]
```

---

## 6. 설정 파일 (건축가 편집 가능, 코드 수정 불필요)

> 아래 6.1~6.3 외에, S/T 시리즈 규칙도 전부 외부 JSON이다(원칙 7): `cross_context.json`(S2 교차 시사점)·`driver_rules.json`(T2 드라이버·가중치)·`archetype_rules.json`(T1.5 동네 유형)·`program_rules.json`(T3 POR 카테고리)·`methodology.json`(T5 방법론 부록 출처 카탈로그·산정식·도메인 매핑). 스키마·동작은 각 파일 `_meta` 및 CLAUDE.md §8.12 참조.

### 6.1 matrix.json — 용도별 지표

```jsonc
{
  "_common": [   // 모든 용도 공통 (에어코리아 등)
    { "item": "PM2.5", "source_type": "airkorea", "method": "realtime", ... }
  ],
  "주거": [
    {
      "item": "고령인구비율",
      "source_type": "kosis",
      "method": "age_share",    // "direct|age_share|age_dependency|ratio|unconfirmed|realtime"
      "age_min": 65,
      "kosis": { "orgId": "101", "tblId": "DT_1B04005N", "itmId": "T2", "objL2": "ALL" },
      "region_scheme": "reg",   // "reg"(행안부코드, 기본) | "census"(인구총조사코드)
      "priority": 1,            // 1(필수) ~ 3(선택)
      "min_resolution": "시군구",
      "freq": "1년",
      "unit": "%"
    }
  ]
}
```

**method 레시피:**
| method | 계산 | 비고 |
|--------|------|------|
| `direct` | 테이블 값 직접 추출 | |
| `age_share` | (age_min~age_max 합계) / 총인구 × 100 | % |
| `age_dependency` | (65세+) / (15~64세) × 100 | 노년부양비 % |
| `ratio` | `num_itm` / `den_itm` × 100 | 1인가구비율 등 |
| `realtime` | 에어코리아 현재값 | 오늘 날짜 기준 |
| `unconfirmed` | 건너뜀 + notes 기록 | 아직 tblId 미확정 |

**region_scheme:**
- `"reg"` (기본): sgg_code = 행안부 시군구 코드 (예: 영등포구 11560)
- `"census"`: 인구총조사 코드 (예: 영등포구 11190) — 테이블마다 다름

### 6.2 implications.json — 함의 규칙

```jsonc
[
  {
    "when": {
      "item": "고령인구비율",
      "op": ">",            // ">" | ">=" | "<" | "<="
      "vs": "national",     // national_avg ± margin 기준
      "margin": 5
    },
    "use_types": ["주거", "의료"],  // 빈 배열 = 전 용도
    "then": "무장애 동선·휴게공간 검토",
    "tag": "참고"
  }
]
```

### 6.3 supply_demand.json — 수급진단 규칙

```jsonc
{
  "rules": [
    {
      "name": "보육시설 수급",
      "demand_item": "유소년인구비율",     // matrix.json 의 item 이름
      "supply_kinds": ["어린이집", "유치원"],
      "demand_margin": 1,
      "supply_low_max": 3,               // radius=1000m 기준; 다른 반경은 (r/1000)² 스케일
      "supply_high_min": 10,
      "national_density_per_10k": 7.7,  // 만명당 전국 평균 시설수 (참고)
      "national_density_source": "어린이집 31,272 + 유치원 8,660 / 51,720,611명",
      "density_low_pct": 60,            // 전국 60% 미만 = 밀도 "적음"
      "density_high_pct": 150,
      "capacity_source": "childcare",   // 시군구 정원 보강 (어린이집만 현재 지원)
      "tag": "참고"
    }
  ]
}
```

**현재 6개 규칙:** 보육시설·노인복지시설·1인가구 생활시설·의료시설·초등학교·문화시설(생산가능인구비율×도서관·미술관·박물관·문화센터·공연장·영화관)

---

## 7. 외부 API 목록

| API | 역할 | 키 | 한계·주의 |
|-----|------|----|---------| 
| 카카오 로컬 | 주소→좌표, 시설 키워드 검색 | `KAKAO_KEY` | 45건/요청 상한 → 적응 분할 |
| JUSO (행안부) | 주소 정규화·법정동코드 폴백 | `JUSO_API_KEY` | 현재 dev키 → 배포 전 운영키 필요 |
| VWorld | 위성 타일, 시설 검색, 공시지가(PNU) | `VWORLD_KEY` | 개발키 2026-12-26 만료 |
| KOSIS OpenAPI | 시군구 인구·가구 통계 | `KOSIS_KEY` | 분당 호출 제한 → 캐시 우선 |
| Claude API | 문단 서술(모드A) · 물어보기(P10) · 종합 산출(S4) | `ANTHROPIC_API_KEY` | Claude 하나(원칙6): narrative·ask=Opus, S4 ①=Sonnet ②=Opus |
| TMAP (SK) | 보행자 경로 → 등시선 | `TMAP_KEY` | 48 병렬 호출 (~0.8s) |
| 에어코리아 | PM2.5·PM10·O3·NO2 | `DATA_GO_KR_API_KEY` | 측정소검색 미승인 → 시도 전체 매칭 |
| 국토부 RTMS | 실거래가 4종 | `DATA_GO_KR_API_KEY` | 데이터셋별 승인 별도 |
| 건축HUB | 건축물대장 | `DATA_GO_KR_API_KEY` | 구버전 미승인, HUB 버전 사용 |
| R-ONE (부동산원) | 매매가격지수 | `RONE_KEY` | |
| 기상청 KMA | 단기예보 | `KMA_KEY` | timeout 35s |
| NEIS | 학교 목록 | `NEIS_KEY` | |
| 상가(상권)정보 | 반경 내 점포수 | `DATA_GO_KR_API_KEY` | B553077 |
| 서울 생활인구 | 행정동별 생활인구 | `SEOUL_API_KEY` | **서울시 전용**, 최신 ~5일 지연 |
| KOPIS | 공연시설 | `KOPIS_KEY` | 키 갱신 후 작동 |
| 어린이집 (정보공개포털) | 시군구 어린이집 개수·정원 | `CHILDCARE_INFO_KEY` | cpmsapi021, XML |
| 문화기반시설총람 | 박물관·미술관 등 10종 | `DATA_GO_KR_API_KEY` | B553457 |
| OSM Overpass | 공공시설 보충 | 없음(무료) | rate-limit, 재시도 없음 |

---

## 8. 데이터 흐름

```
주소 입력
    │
    ▼
resolve_address()  ─────────────────────────── 카카오 + JUSO
    │ ResolvedAddress(lat, lon, sgg_code, bcode, sido, sigungu, ...)
    ├────────────────────────────────────────────────────────────┐
    ▼                                                            ▼
[모드 A: 지역 통계]                              [모드 B: 주변 시설]
collect_facts()                                  build_facility_result()
    │                                                    │
    ├─ KOSIS fetch (matrix.json 항목별)                  ├─ 카카오 검색 (적응 분할)
    ├─ 에어코리아 fetch                                  ├─ OSM 보충
    ├─ implications.json 룩업                            └─ VWorld 보충
    └─ compose_narrative() → Claude 1회                      │
         │                                                    │ counts{}
         ▼                                                    │
     RegionStat                                               │
                                                             │
    ┌────────────────────────────────────────────────────────┘
    │ facts[] + counts{}
    ▼
[P11: 수급진단]
cross_rules(facts, band, radius)
    ├─ supply_demand.json 규칙 6개
    ├─ _supply_level_count() — 반경² 스케일
    ├─ _supply_level_density() — 전국 만명당 비교 (참고)
    └─ → diagnoses[]

    │ diagnoses[]
    ▼
[P10: 물어보기] ← gather_bundle(A+B+P11) → Claude 그라운디드 답변
[P9: 비교]     ← 후보지 N개 각 A+B+P11 → 나란히

[모드 B 지도]
compose_map()
    ├─ tmap.compute_isochrone() → 16방향×3시간 폴리곤
    ├─ PIL 위성타일 합성
    └─ PNG 저장 → URL
```

---

## 9. 캐싱 전략

```python
class Cache:  # 추상 인터페이스
    def get(key) → Optional[dict]
    def set(key, value, ttl=None)

# 구현체
FileCache(directory)    # 로컬 (JSON 파일)
MemoryCache()           # 단위테스트용
GCSCache(bucket)        # Cloud Run 멀티 인스턴스 (선택)
```

**캐시 키 패턴:**
- KOSIS: `(orgId, tblId, region_code, year, itmId, objL2)`
- 에어코리아: `airkorea:{sido}:{sigungu}:{today}` (하루 TTL — sido 포함으로 동명 시군구(중구 등) 오염 방지)
- 타일: 좌표+줌 (영구)

**KOSIS 동일 테이블 한 번만 호출:**
- 연령 구조 5지표(고령·유소년·생산가능·노년부양비·총인구) → `DT_1B04005N` 1회
- `fetch_total_pop()`도 동일 테이블 캐시 재사용 — 추가 API 호출 없음

---

## 10. 에러 처리 원칙

| 상황 | 처리 |
|------|------|
| 주소 해석 불가 | `ErrorBlock(ADDR_UNRESOLVED)` + HTTP 422 (하드블록) |
| 지역코드 없음 | `ErrorBlock(NO_REGION_CODE)` + HTTP 422 |
| 데이터 없음 (지표 전부) | `ErrorBlock(NO_DATA)` + HTTP 422 |
| 일부 API 실패 | `notes[]` 기록 + 부분 반환 (graceful — 원칙 3) |
| 비상업 시설 검색 실패 | `notes[]` 기록 + 카카오 결과만 반환 |
| TMAP 실패 | `notes[]` 기록 + 반경원 폴백 |
| Claude API 실패 | `source: "rule_based_fallback"` + 규칙 문단 |
| 후보지 한 개 실패 | `CompareSite.error` 기록 + 나머지 계속 |

**공통 패턴:** "전체 죽이기" 금지. 부분 실패는 격리하고, 성공한 부분은 반환.

---

## 11. 한계 (실측·추론)

### 11.1 데이터 공간 해상도

- **KOSIS 통계는 시군구 평균** — 대지 고유값이 아님. "영등포구 기준"이지 여의도동 기준이 아님
- 읍면동 단위 통계는 대부분 KOSIS에 존재하지 않거나 별도 지역코드 체계가 필요
- 반경 내 인구는 계산 불가 → 공급 판정의 분모를 시군구 전체 인구로 사용 (공간 불일치)

### 11.2 수급진단 임계값 한계

- `supply_low_max`, `supply_high_min`은 휴리스틱 (JSON에 근거 출처 없음, 반경 1km 기준)
- 전국 밀도(`national_density_per_10k`)의 분모·분자가 다른 공간 단위 → 절대 숫자 비교는 의미 제한
- 문화시설 수급은 생산가능인구비율을 수요 proxy로 편입(6번째 규칙) — 단일 proxy라 약함·도심 동반상승 한계(note 명시). 상업 시설은 단일 수요 지표가 없어 여전히 수급진단 미편입

### 11.3 시설 검색 한계

- 카카오 45건 상한 → 적응 분할로 부분 해소했으나 매우 밀집된 지역은 누락 가능성
- 카카오 키워드 매칭 오류 가능성 (비슷한 이름, 폐업 정보 지연 등)
- VWorld 시설 검색은 경로당·노인복지관·마을회관에만 국한 (`KIND_TO_VWORLD` 매핑)
- OSM 데이터는 지역별 갱신 주기가 다름 (공신력 낮을 수 있음) [추정]

### 11.4 등시선 한계

- TMAP 보행자 경로 없는 방향 → 꼭짓점 제외 → 폴리곤 들쭉날쭉 가능
- 16방향 고정 → 실제 보행가능 경계와 오차 (방향 밀도 한계)
- 시간당 호출 제한(TMAP API)에 도달하면 부분 실패 [추정]

### 11.5 지역 제한

- **서울 생활인구: 서울시 전용.** 다른 시도에서는 `null` 반환
- KOPIS 공연시설은 `signgucode = 행안부 sgg_code[:4]` 서버측 필터 (2026-06-30 실API 검증). 이전 이름필터(전국 1000건 상한·동명 오매칭)는 폴백
- 실거래 데이터는 거래가 없는 기간·지역에서 0건 반환

### 11.6 KOSIS 미확정 지표 (matrix.json method:"unconfirmed" 건너뜀)

- 인구밀도 — 시군구 단위 면적 테이블 결합 필요
- 주택보급률·주간인구지수 — tblId 미확정
- ~~사업체수·종사자수~~ → **해결**: `census_multidim` 차원 크랙으로 시군구 사업체수(DT_1BD1032,
  영등포 96,993)·종사자수·빈집·신혼부부·등록장애인 등 다차원 census 표 질의 가능. `/readout`이 제공.
  (matrix.json 정식 편입은 후속 — 현재는 순이동·세대수만 편입, 나머지는 readout 경로.)
  관련 자산: `docs/KOSIS_DEPTH_PLAN.md`·`docs/KOSIS_INDICATOR_DICTIONARY.md`·`scripts/{mine_kosis_catalog,
  shortlist_kosis,profile_kosis_dims,demo_site_kosis}.py`

### 11.7 앱이 명시적으로 안 만드는 것

- 물리 시뮬레이션 (일조·바람·그림자)
- 재무 분석 (사업수지·NPV·분양가)
- 규제 해석 ("이 용도지역에 뭘 지을 수 있는가" 판단)
- 설계 안 생성

### 11.8 기술 부채

- `httpx` + `starlette.testclient` 조합 deprecation 경고 (httpx2 필요)
- GCS 캐시 + TTL 미구현 (Cloud Run 멀티 인스턴스 환경)
- 합성 PNG 저장이 인스턴스 로컬 파일시스템 → `/tmp` 의존 (인스턴스 재시작 시 소실) [추정]
- JUSO 운영키 미교체 (현재 dev키)

---

## 12. 테스트 전략

```
tests/
  test_smoke.py          # /health, /matrix 최소 스모크
  test_cache.py          # 캐시 라운드트립 (GCS 포함, 네트워크 없음)
  test_diagnose.py       # cross_rules 순수 로직 + 전체 흐름 모킹
  test_stats_compute.py  # 연령비율·부양비·비율 계산 결정적 검증
  test_geo.py            # 하버사인·반경밴드
  test_tiles.py          # 좌표↔픽셀 변환, 줌 계산
  test_modea_config.py   # matrix/implications JSON 로드
  test_narrative.py      # 규칙 폴백 (Claude 실호출은 skipif)
  test_http_retry.py     # 백오프 재시도 로직 (MockTransport)
  test_*_live.py         # 실제 API (KOSIS·카카오 키 있을 때만 skipif)
```

**패턴:**
- 순수 로직 → 네트워크 없이 결정적 검증
- 전체 흐름 → `monkeypatch` 로 외부 서비스 대체
- 실제 API → `@pytest.mark.skipif(not KEY)` 분리

---

## 13. 배포 구조

**단일 서비스:** FastAPI가 `frontend/dist` 정적 서빙 → URL 하나, CORS 불필요

```
Cloud Run
├── FastAPI (0.0.0.0:8080)
│   ├── POST /analyze, /facilities, ...  (백엔드)
│   └── GET  /*                          (React SPA 서빙)
├── Secret Manager (키 주입, .env 커밋 금지)
├── GCS bucket (캐시 — 선택, 로컬 FileCache 폴백)
└── OUT_DIR=/tmp/out (PNG 저장)
```

**로컬 개발:**
```powershell
# 백엔드
.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# 프론트 (별도 터미널, Vite 프록시 → localhost:8000)
cd frontend && npm run dev
```

---

## 14. 설계 결정 이유 [추정]

| 결정 | 추정 이유 |
|------|---------|
| `supply_low_max`·`supply_high_min`을 JSON에 둔 것 | 건축가가 현장 피드백으로 임계값을 조정할 수 있게 — 코드 배포 없이 |
| 모드 C 공급 판정을 밀도가 아닌 개수 기반으로 한 것 | 분모(시군구 전체인구) ≠ 분자(반경 내 시설)의 공간 불일치 — 절대 오류보다 상대 오류가 작은 개수 기반이 더 안전 |
| Claude 모델을 하나만 쓴 것 | 정답이 정해진 데이터에서 다중 모델 교차는 잡음만 늘림 (원칙 6) |
| 함의(implications)를 LLM이 아닌 규칙으로 만든 것 | LLM이 새 수치를 생성하지 않도록 — 규칙은 재현 가능하고 감사 가능 |
| 수급진단에 종합점수를 두지 않은 것 | "좋다/나쁘다" 단정은 설계 판단 — 그 판단은 건축가가 해야 함 (원칙 5) |
| OSM·VWorld를 보충 소스로 쓴 것 | 카카오 45건 상한 + 비상업 시설(경로당 등) 누락 보완 |
| 서울 생활인구만 서울 전용인 것 | SEOUL_API 자체가 서울시 데이터만 제공 — 다른 시도엔 해당 API 없음 |
| TMAP 등시선에서 반경 2.5배 오프셋을 쓴 것 | 직선 거리보다 실제 도로 우회 경로가 길기 때문 — 2.5는 도시 도로 굴곡율 경험치 [추정] |

---

> CLAUDE.md §2 차별점 체크리스트를 새 기능 추가 시 반드시 통과시킬 것.
> 전체 API 목록·검증 현황은 `API_MASTER_LIST.md` 및 `docs/API_VERIFICATION_*.md` 참조.
