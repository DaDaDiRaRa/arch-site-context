# 터읽기 (arch-site-context)

**대지 주소 하나로, 그 동네를 여러 방식으로 읽어주는 건축 대지분석 웹앱.**

건축가가 설계 시작 전 반나절 걸려 하던 '대지 주변 조사'를 — 인구·시설·수급·날씨·상권·학교·부동산지수까지 — 주소 한 줄로 표·문단·지도·진단·비교까지 자동 생성한다. **최종 설계 판단은 사람이 한다.**

---

## 기능 한눈에 보기

| 탭 | 기능 | 설명 |
| --- | --- | --- |
| **I** | **종합 읽기** ★ | 주소 → 인구·수급·재해·대지·생활맥락을 한 번에 + **동네 유형·설계 드라이버·프로그램 함의·AI 종합해석**. 공유·인쇄용 보드 내보내기 (S/T 시리즈) |
| A | **지역 통계** | 주소 + 건물 용도 → 용도에 맞는 인구·세대·경제 통계 + 시사점 + 한 문단 초안. 각 수치에 **전국=100 지수·근접도** + 클릭 시 근거 |
| B | **주변 시설** | 주소 + 시설종류 + 반경(500/1000/2000m) → 시설 목록·개수 + 위성사진 PNG(핀·TMAP 실도보 등시선) |
| C | **수급 진단** ★ | A(인구 수요) × B(시설 공급) 교차 → "무엇이 부족/과잉인가" 근거·반경비례·전국밀도 제시 |
| D | **후보지 비교** | 여러 대지 동시 입력 → A·B·수급진단 나란히 비교 (종합점수 없음, 판단은 사람) |
| E | **물어보기** | 위 데이터 위에서만 자연어 질문에 답변. 데이터 밖이면 "확인 불가"로 멈춤 |
| F | **대지 정보** | 주소 → 개별공시지가(필지)·실거래·건축물대장(건폐율·용적률) |
| G | **보드 합본** | 주소 → 상권·학교·어린이집·문화시설·부동산지수·날씨·생활인구·공연시설 한 화면 |
| H | **공동주택 readout** | 재건축·재개발·민간 부지 → 인구·산업·주거·복지 종합 프로파일 + 유형별 ★강조 (전국, KOSIS 다차원) |

---

## 절대 원칙 (이 앱의 존재 이유)

1. **추출, 해석하지 않는다** — 값은 실제 API에서 호출해 가져온다. AI 기억·추정 금지.
2. **숫자는 코드, 표현만 AI** — 수치·함의·수급 신호·설계 드라이버·프로그램 함의·동네 유형은 전부 코드/규칙이 만든다. LLM은 문장 표현만.
3. **확인 불가 하드블록** — 데이터로 답할 수 없으면 추정하지 않고 "확인 불가"로 멈춘다.
4. **출처·기준 명시** — 모든 수치에 출처(통계표 ID/API)·기준연도·근접도(대지>반경>읍면동>시군구>proxy) 표기.
5. **판단은 분리·라벨하되 최종 결정은 사람** — 검증된 사실과 AI 의견을 **벽으로 분리·라벨**해 제시(종합 읽기 ①사실 ②AI의견). 좋다/나쁘다·사업성 금액 단정은 금지, 종합점수·순위 없음. 최종 결정은 사람.
6. **모델은 Claude 하나** — 다벤더·교차검증 금지. (Claude 계열 내 티어 분리는 허용: 종합해석 ①서술=Sonnet·②판단=Opus.)
7. **설정은 JSON, 코드 아님** — 용도 목록·함의·수급·교차규칙·설계 드라이버·프로그램·동네 유형 규칙은 전부 외부 JSON. 건축가가 코드 없이 편집.

---

## 종합 읽기 — `/board` (S/T 시리즈)

흩어진 출력을 **하나의 "이 필지는 어떤 곳인가"**로 합성한다. 기존 서비스(analyze·diagnose·site·seed)를 병렬 오케스트레이션만 하고(새 데이터 0), 그 위에 해석 레이어를 얹는다.

- **S1 데이터 근접도** — 모든 수치에 `대지 > 반경 > 읍면동 > 시군구 > proxy` 등급. "구 평균은 대지값 아님"을 기계가독으로.
- **S2 교차규칙** — 도메인 횡단 '참고' 시사점 (예: 고령↑+의료 부족 → 의료 접근성 검토). 규칙 매칭, LLM 0.
- **S4 종합 산출** — 사실과 AI 의견을 **벽으로 분리·라벨**. ①사실 종합(Sonnet, 그라운디드) + ②AI 판단(Opus, 근거 인용·가정 명시·새 숫자 금지). 데이터 없으면 생성 안 함.
- **T1 정규화 지수** — 전국=100 지수 막대 + 지표 클릭 시 근거(출처·근접도·연도) 드릴다운.
- **T1.5 대지 아키타입** — "이 동네는 ○○형"(1인가구 도심 임대권·고령 정주형 등). 규칙 룩업(K-means 아님).
- **T2 설계 드라이버** — 통합 풀을 증거강도로 랭킹 → 지배 설계 드라이버 2~3개(검토 신호).
- **T3 프로그램 함의(POR)** — 맥락 → 건축 카테고리별(평면·코어·공용부·저층부·방재…) 공간·프로그램 권고.
- **T4 보드 내보내기** — 지도 앵커 + 위 전부를 **자체완결 한 장 HTML**로. 공유 링크·인쇄(PDF). `POST /board/view`.

**딜리버리 3종:** ① 탐색 대시보드(I탭) · ② API/**MCP 서버**(`mcp_server/`, Claude·에이전트가 `read_site_context`로 호출) · ③ 공유 보드(링크·PDF).
**형제앱 연동:** 설계공모 제안서 앱 **competition_comparison** 이 `/board {brief:true}` 를 pull → 수주 제안서 대지분석을 실측화 (상세 [INTEGRATION.md](INTEGRATION.md)).

---

## 사용 API

| API | 역할 | 비고 |
| --- | --- | --- |
| **카카오 로컬** | 주소→좌표, 반경 시설 키워드 검색 | 모드 B 핵심 |
| **TMAP (SK)** | 보행자 경로 기반 실도보 등시선 (5·10·15분 권역) | `/facilities/map` 옵션 |
| **JUSO (행안부)** | 주소 정규화·법정동코드 폴백 | 카카오 0건 시 |
| **VWorld** | 위성 타일 PNG, 경로당·노인복지시설 검색, 개별공시지가(필지) | 타일: WMTS Satellite |
| **KOSIS OpenAPI** | 시군구/읍면동 인구·가구 통계 (연령 5지표 + 1인가구비율·순이동·세대수 등, census 다차원) | 캐시 우선, 분당 제한 |
| **SGIS (통계청)** | 반경 집계구 실인구(수급진단 반경 모드) · 재해위험(홍수·산사태 영향범위·폭염 이력) | 좌표+반경 실인구 합산·보간 금지 |
| **Claude API** | 한 문단 서술(모드 A) · 물어보기 그라운디드 답변(모드 E) · **종합 산출**(①사실=Sonnet ②AI판단=Opus, 종합 읽기) | Claude 하나, 그라운디드·환각 방지 |
| **에어코리아** | PM2.5·PM10·O3·NO2 실측값 | 시도 전체→시군구명 매칭 |
| **국토부 실거래(MOLIT)** | 토지매매·아파트매매·연립다세대·전월세 각 5건 | 승인된 RTMS 엔드포인트 |
| **건축HUB** | 건축물대장 (표제부·총괄표제부 → 연면적·건폐율·용적률) | PNU 기반 |
| **R-ONE (부동산원)** | 매매가격지수 지역별 시계열 | 최신 시점 자동 |
| **기상청 (KMA)** | 단기예보 기온·강수확률·하늘상태 | 좌표→격자 변환 |
| **NEIS** | 시군구 내 학교 목록·종류별 집계 | |
| **상가(상권)정보** | 반경 내 점포수·업종 대분류 집계 | data.go.kr B553077 |
| **서울 생활인구** | 행정동별 생활인구 (최신 가용일 자동) | 서울시 전용 |
| **KOPIS** | 공연시설 목록 | |
| **정보공개포털 (어린이집)** | 시군구별 어린이집 개수·총정원 | cpmsapi021 |
| **문화기반시설총람** | 박물관·미술관·도서관 등 10종 시군구별 집계 | data.go.kr B553457 |

---

## 엔드포인트

| 메서드 | 경로 | 기능 |
| --- | --- | --- |
| `GET` | `/health` | 헬스체크 |
| `GET` | `/matrix` | 용도별 항목 목록 (투명성) |
| `POST` | `/facilities` | 반경 시설 목록·개수 |
| `POST` | `/facilities/map` | 위성 PNG (핀·TMAP 보행자 등시선 또는 반경원·범례) |
| `POST` | `/analyze` | 지역 통계 + 함의 + 한 문단 초안 |
| `POST` | `/diagnose` | 수급 진단 (A수요 × B공급 교차) ★ |
| `POST` | `/compare` | 여러 후보지 A·B·수급진단 나란히 |
| `POST` | `/ask` | 물어보기 (데이터 위에서만 + 웹검색 opt-in) |
| `POST` | `/site` | 대지 기본정보 (공시지가·실거래·건축물대장) |
| `POST` | `/seed` | 보드 합본 — site + 상권·학교·부동산지수·날씨·생활인구·공연 |
| `POST` | `/readout` | 공동주택 대지 readout — 인구·산업·주거·복지 종합 + 유형 프리셋 (KOSIS 다차원) |
| `POST` | `/board` | **종합 읽기** ★ — 병렬 오케스트레이션 + 근접도·교차규칙·설계 드라이버·프로그램 함의·동네 유형·(opt-in) AI 종합. `brief:true` 압축 투영(형제앱·MCP용) |
| `POST` | `/board/view` | **보드 내보내기** — /board → 지도·드라이버·POR·종합 담긴 자체완결 한 장 HTML → `/files` 공유 URL (인쇄→PDF) |

MCP 서버: `claude mcp add teoilgi python mcp_server/server.py` (도구: `read_site_context`·`diagnose_supply`)

대화형 API 문서: 서버 실행 후 `http://127.0.0.1:8000/docs`

---

## 입력 / 출력 예시

### 모드 A — 지역 통계

요청:

```json
POST /analyze
{
  "address": "서울특별시 영등포구 여의대로 24",
  "use_type": "주거"
}
```

응답:

```json
{
  "region": { "name": "영등포구", "code": "11560", "resolution": "시군구" },
  "facts": [
    { "item": "1인가구비율", "value": 45.1, "national_avg": 36.1, "unit": "%",
      "source_tbl": "DT_1JC1511", "year": 2024,
      "scope": "영등포구", "proximity": "시군구", "index": 125, "index_band": "상회" },
    { "item": "고령인구비율", "value": 19.2, "national_avg": 21.2, "unit": "%",
      "source_tbl": "DT_1B04005N", "year": 2025,
      "scope": "영등포구", "proximity": "시군구", "index": 91, "index_band": "비슷" }
  ],
  "implications": [
    { "text": "소형 평형·공유공간 검토", "basis": "1인가구비율", "tag": "참고" }
  ],
  "draft_paragraph": "영등포구 기준(시군구 근접도), 1인가구 비율이 전국 대비 지수 125로 높아..."
}
```

### 모드 B — 주변 시설

요청:

```json
POST /facilities
{
  "address": "서울특별시 영등포구 여의대로 24",
  "kinds": ["어린이집", "경로당"],
  "radii": [500, 1000, 2000]
}
```

응답:

```json
{
  "counts": {
    "500":  { "어린이집": 3, "경로당": 12 },
    "1000": { "어린이집": 8, "경로당": 35 }
  },
  "source": "kakao+vworld"
}
```

### 수급 진단

요청:

```json
POST /diagnose
{
  "address": "서울특별시 영등포구 여의대로 24",
  "radius": 1000
}
```

응답:

```json
{
  "diagnoses": [
    {
      "name": "보육시설 수급",
      "demand": { "item": "유소년인구비율", "value": 8.3, "national_avg": 10.3, "level": "낮음" },
      "supply": {
        "kinds": ["어린이집", "유치원"], "count": 23, "level": "많음",
        "density_per_10k": 0.62, "national_density_per_10k": 7.7, "vs_national_pct": 8,
        "capacity": 2785, "capacity_scope": "영등포구"
      },
      "signal": "수요 낮음·공급 많음",
      "tag": "참고"
    }
  ]
}
```

`supply.level`은 반경² 스케일 임계값(반경 2km → 4배 확대)으로 판정. `density_per_10k`·`vs_national_pct`는 전국 기준 대비 밀도를 참고용으로 함께 제공. 원칙상 판단은 사람.

> 현재 수급진단 규칙 6개: 보육·노인복지·1인가구 생활·의료·초등학교·문화시설.

---

## 기술 스택

- **백엔드**: FastAPI (Python 3.11)
- **프론트**: React + Vite + Tailwind CSS
- **배포**: GCP Cloud Run + Secret Manager + GCS(캐시)
- **설정 파일** (코드 없이 건축가가 수정 — 원칙 7):
  - `app/data/matrix.json` — 용도별 통계 항목 목록
  - `app/data/implications.json` — 단일 지표 함의 규칙
  - `app/data/supply_demand.json` — 수급 진단 임계값
  - `app/data/cross_context.json` — S2 도메인 횡단 교차 시사점 규칙
  - `app/data/driver_rules.json` — T2 설계 드라이버 규칙·가중치
  - `app/data/archetype_rules.json` — T1.5 대지 아키타입(동네 유형) 규칙
  - `app/data/program_rules.json` — T3 프로그램 함의(POR) 카테고리별 규칙

---

## 로컬 실행 (Windows)

```powershell
# 1) venv 생성 (정식 설치본 Python 3.11, Microsoft Store python 금지)
C:\Users\<you>\AppData\Local\Programs\Python\Python311\python.exe -m venv D:\APPS\arch-site-context\.venv

# 2) 의존성 설치
D:\APPS\arch-site-context\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3) 키 설정
copy .env.example .env   # 값 채우기

# 4) 서버 실행
D:\APPS\arch-site-context\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# 5) 프론트 개발 서버 (별도 터미널)
cd frontend && npm install && npm run dev
```

## 테스트

```powershell
D:\APPS\arch-site-context\.venv\Scripts\python.exe -m pytest -q
```

---

## 배포 (GCP Cloud Run)

프론트(`frontend/dist`)를 백엔드가 정적 서빙 — URL 하나, CORS 불필요.

```bash
# 시크릿 등록 (1회)
for K in KAKAO_KEY VWORLD_KEY KOSIS_KEY ANTHROPIC_API_KEY JUSO_API_KEY; do
  printf "%s" "$(grep "^$K=" .env | cut -d= -f2-)" | \
    gcloud secrets create $K --data-file=- 2>/dev/null || \
  printf "%s" "$(grep "^$K=" .env | cut -d= -f2-)" | \
    gcloud secrets versions add $K --data-file=-
done

# 배포
gcloud run deploy arch-site-context \
  --source . \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --memory 512Mi \
  --set-env-vars OUT_DIR=/tmp/out,GCS_CACHE_BUCKET=<PROJECT_ID>-arch-cache \
  --set-secrets KAKAO_KEY=KAKAO_KEY:latest,...
```

---

## 폴더 구조

```text
arch-site-context/
├── app/
│   ├── main.py              # FastAPI 진입점
│   ├── routers/             # 엔드포인트별 라우터
│   ├── services/            # 외부 API 호출·계산 로직
│   │   ├── facilities.py    #   반경 시설 (카카오 + VWorld 병합)
│   │   ├── kakao.py         #   카카오 로컬 API
│   │   ├── kosis.py         #   KOSIS 통계 + 캐시
│   │   ├── vworld.py        #   VWorld 타일·검색·공시지가
│   │   ├── molit.py         #   실거래·건축물대장
│   │   ├── airkorea.py      #   대기질
│   │   ├── kma.py           #   기상청 단기예보
│   │   ├── rone.py          #   부동산원 가격지수
│   │   ├── neis.py          #   학교 정보
│   │   ├── sangwon.py       #   상가(상권)정보
│   │   ├── seoul.py         #   서울 생활인구
│   │   ├── kopis.py         #   공연시설
│   │   ├── childcare.py     #   어린이집 개수·정원
│   │   ├── culture.py       #   문화기반시설총람 10종
│   │   ├── tmap.py          #   TMAP 보행자 경로 → 실도보 등시선 폴리곤
│   │   ├── sgis.py          #   SGIS 반경 집계구 실인구 · 재해위험(홍수·산사태·폭염)
│   │   ├── diagnose.py      #   수급 진단 (A×B 교차, 반경비례 임계값)
│   │   ├── cross_context.py #   S2 도메인 횡단 교차 시사점 엔진
│   │   ├── design_drivers.py#   T2 설계 드라이버 랭킹 엔진
│   │   ├── archetype.py     #   T1.5 대지 아키타입 분류
│   │   ├── program.py       #   T3 프로그램 함의(POR) 엔진
│   │   ├── synthesis.py     #   S4 종합 산출 (①사실=Sonnet ②AI판단=Opus)
│   │   ├── board_contract.py#   /board 공유 계약 (board_brief·project_seed)
│   │   ├── board_view.py    #   T4 대지분석 보드 HTML 렌더
│   │   ├── site_seed.py     #   보드 합본 진입점
│   │   ├── census_multidim.py #  KOSIS 다차원 census 지표 (getMeta 차원해부, 사업체·빈집 등)
│   │   └── readout.py       #   공동주택 대지 readout 오케스트레이션
│   ├── schemas/             #   Pydantic v2 데이터 계약 (proximity·board·design_drivers·archetype·program 등)
│   └── data/                #   외부 JSON 설정 (건축가 편집 — 원칙 7)
│       ├── matrix.json · implications.json · supply_demand.json
│       └── cross_context.json · driver_rules.json · archetype_rules.json · program_rules.json
├── mcp_server/              # 터읽기 MCP 서버 (read_site_context·diagnose_supply)
├── frontend/                # React + Vite + Tailwind (TabA~I, I=종합 읽기)
├── tests/                   # pytest (단위 + 라이브 테스트)
├── scripts/                 # 유틸 스크립트 (KOSIS 카탈로그 마이너·차원 프로파일러·readout 데모 등)
├── docs/                    # API 검증 기록 + KOSIS 깊이확장 계획·지표사전
├── API_MASTER_LIST.md       # 전체 데이터 소스 목록 (~161개)
├── CLAUDE.md                # 아키텍처·원칙·로드맵 (AI용)
└── INTEGRATION.md           # 형제앱 연동 계약
```

---

> 상세 원칙·로드맵·API 검증 현황은 [CLAUDE.md](CLAUDE.md) 참조.
> 전체 데이터 소스 목록(~161개)은 [API_MASTER_LIST.md](API_MASTER_LIST.md) 참조.
