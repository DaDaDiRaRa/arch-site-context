# 터읽기 (arch-site-context)

**대지 주소 하나로, 그 동네를 여러 방식으로 읽어주는 건축 대지분석 웹앱.**

건축가가 설계 시작 전 반나절 걸려 하던 '대지 주변 조사'를 — 인구·시설·수급·날씨·상권·학교·부동산지수까지 — 주소 한 줄로 표·문단·지도·진단·비교까지 자동 생성한다. **최종 설계 판단은 사람이 한다.**

---

## 기능 한눈에 보기

| 탭 | 기능 | 설명 |
| --- | --- | --- |
| A | **지역 통계** | 주소 + 건물 용도 → 용도에 맞는 인구·세대·경제 통계 + 시사점 + 한 문단 초안 |
| B | **주변 시설** | 주소 + 시설종류 + 반경(500/1000/2000m) → 시설 목록·개수 + 위성사진 PNG(핀·반경) |
| C | **수급 진단** ★ | A(인구 수요) × B(시설 공급) 교차 → "무엇이 부족/과잉인가" 근거 제시 |
| D | **후보지 비교** | 여러 대지 동시 입력 → A·B·수급진단 나란히 비교 (종합점수 없음, 판단은 사람) |
| E | **물어보기** | 위 데이터 위에서만 자연어 질문에 답변. 데이터 밖이면 "확인 불가"로 멈춤 |

---

## 절대 원칙 (이 앱의 존재 이유)

1. **추출, 해석하지 않는다** — 값은 실제 API에서 호출해 가져온다. AI 기억·추정 금지.
2. **숫자는 코드, 표현만 AI** — 수치·함의·수급 신호는 코드/룩업이 만든다. LLM은 문장 표현만.
3. **확인 불가 하드블록** — 데이터로 답할 수 없으면 추정하지 않고 "확인 불가"로 멈춘다.
4. **출처·기준 명시** — 모든 수치에 출처(통계표 ID/API)·기준연도·"○○구 기준" 표기.
5. **판단은 사람** — 좋다/나쁘다·사업성 단정 금지. 재료와 근거만 제시.

---

## 사용 API

| API | 역할 | 비고 |
| --- | --- | --- |
| **카카오 로컬** | 주소→좌표, 반경 시설 키워드 검색 | 모드 B 핵심 |
| **JUSO (행안부)** | 주소 정규화·법정동코드 폴백 | 카카오 0건 시 |
| **VWorld** | 위성 타일 PNG, 경로당·노인복지시설 검색, 개별공시지가(필지) | 타일: WMTS Satellite |
| **KOSIS OpenAPI** | 시군구 단위 인구·가구 통계 (5지표 + 1인가구비율 등) | 캐시 우선, 분당 제한 |
| **Claude API** | 한 문단 서술(모드 A), 물어보기 그라운디드 답변(모드 E) | 모델 하나, 환각 방지 |
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
| `POST` | `/facilities/map` | 위성 PNG (핀·반경원·범례) |
| `POST` | `/analyze` | 지역 통계 + 함의 + 한 문단 초안 |
| `POST` | `/diagnose` | 수급 진단 (A수요 × B공급 교차) ★ |
| `POST` | `/compare` | 여러 후보지 A·B·수급진단 나란히 |
| `POST` | `/ask` | 물어보기 (데이터 위에서만 + 웹검색 opt-in) |
| `POST` | `/site` | 대지 기본정보 (공시지가·실거래·건축물대장) |
| `POST` | `/seed` | 보드 합본 — site + 상권·학교·부동산지수·날씨·생활인구·공연 |

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
  "region": { "name": "영등포구", "code": "11560" },
  "facts": [
    { "item": "1인가구비율", "value": 38.2, "national_avg": 33.4, "unit": "%" },
    { "item": "고령인구비율", "value": 17.1, "national_avg": 18.3, "unit": "%" }
  ],
  "implications": [
    { "text": "소형 평형·공유공간 검토", "basis": "1인가구비율", "tag": "참고" }
  ],
  "draft_paragraph": "영등포구는 1인가구 비율이 전국 평균보다 높아..."
}
```

### 모드 B — 주변 시설

요청:

```json
POST /facilities
{
  "address": "서울특별시 영등포구 여의대로 24",
  "kinds": ["어린이집", "경로당"],
  "radius": 1000
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
      "demand": { "item": "유소년인구비율", "value": 8.3, "level": "낮음" },
      "supply": { "kinds": ["어린이집", "유치원"], "count": 23, "level": "많음" },
      "signal": "수요 낮음·공급 많음",
      "tag": "참고"
    }
  ]
}
```

---

## 기술 스택

- **백엔드**: FastAPI (Python 3.11)
- **프론트**: React + Vite + Tailwind CSS
- **배포**: GCP Cloud Run + Secret Manager + GCS(캐시)
- **설정 파일** (코드 없이 건축가가 수정):
  - `app/data/matrix.json` — 용도별 통계 항목 목록
  - `app/data/implications.json` — 함의 규칙
  - `app/data/supply_demand.json` — 수급 진단 임계값

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
│   │   ├── diagnose.py      #   수급 진단 (A×B 교차)
│   │   └── site_seed.py     #   보드 합본 진입점
│   ├── schemas/             #   Pydantic v2 데이터 계약
│   └── data/                #   외부 JSON 설정 (건축가 편집)
│       ├── matrix.json
│       ├── implications.json
│       └── supply_demand.json
├── frontend/                # React + Vite + Tailwind
├── tests/                   # pytest (단위 + 라이브 테스트)
├── scripts/                 # 유틸 스크립트
├── docs/                    # API 검증 기록
├── API_MASTER_LIST.md       # 전체 데이터 소스 목록 (~161개)
├── CLAUDE.md                # 아키텍처·원칙·로드맵 (AI용)
└── INTEGRATION.md           # 형제앱 연동 계약
```

---

> 상세 원칙·로드맵·API 검증 현황은 [CLAUDE.md](CLAUDE.md) 참조.
> 전체 데이터 소스 목록(~161개)은 [API_MASTER_LIST.md](API_MASTER_LIST.md) 참조.
