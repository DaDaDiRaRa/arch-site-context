# arch-site-context (터읽기)

대지 주소만 넣으면 그 동네가 어떤 곳인지 두 방식으로 읽어주는 웹앱의 백엔드.
건축가의 '대지 분석 보드' 중 인문·주변 파트를 자동으로 채운다. (최종 설계 판단은 사람)

- **모드 A — 지역 통계**: 주소 + 용도 → 용도에 맞는 통계만 골라 표 + 시사점 + 한 문단 초안.
- **모드 B — 주변 시설**: 주소 + 시설종류 + 반경 → 반경 내 시설 목록·개수 + 위성 PNG(핀·반경).

> 현재 **Phase 0 (P0)** — 골격과 데이터 계약(스키마)만. 모든 엔드포인트는 하드코딩 샘플 JSON을 반환한다.
> 실제 API 호출·계산(카카오·VWorld·KOSIS·Claude)은 P1 이후. 자세한 원칙·로드맵은 [CLAUDE.md](CLAUDE.md).

---

## 폴더 구조

```
arch-site-context/
├─ app/
│  ├─ main.py              # FastAPI 진입점 (라우터 등록, CORS, .env 로드)
│  ├─ routers/             # 엔드포인트 (P0: 스텁)
│  │  ├─ health.py         #   GET  /health
│  │  ├─ facilities.py     #   POST /facilities, POST /facilities/map  (모드 B)
│  │  ├─ analyze.py        #   POST /analyze                            (모드 A)
│  │  └─ matrix.py         #   GET  /matrix
│  ├─ services/            # 서버 함수 (흐름의 각 단계) — P0엔 비어 있음. README 참고
│  ├─ schemas/             # pydantic v2 데이터 계약 (+ 예시 JSON)
│  │  ├─ facility.py       #   FacilityRequest, FacilityResult, MapRequest
│  │  ├─ region.py         #   AnalyzeRequest, RegionStat
│  │  └─ errors.py         #   ErrorBlock (하드블록)
│  └─ data/                # 외부 설정 JSON (건축가가 코드 없이 수정)
│     ├─ matrix.json       #   용도별 KOSIS 항목 목록
│     └─ implications.json #   함의 규칙
├─ tests/                  # 스모크 테스트
│  └─ test_smoke.py
├─ scripts/
│  └─ run.ps1              # 로컬 서버 실행
├─ .env.example            # 키 자리 (값 비움)
├─ requirements.txt
└─ CLAUDE.md               # 아키텍처·원칙·로드맵 (작업 전 필독)
```

## 엔드포인트

| 메서드 | 경로 | 모드 | 한 줄 설명 |
|---|---|---|---|
| GET  | `/health`         | -  | 헬스체크 |
| POST | `/facilities`     | B  | 반경 내 시설 목록·개수 (`FacilityResult`) |
| POST | `/facilities/map` | B  | 위성 PNG (핀·반경) — P0는 플레이스홀더 1x1 PNG |
| POST | `/analyze`        | A  | 지역 통계 + 함의 + 문단 초안 (`RegionStat`) |
| GET  | `/matrix`         | A  | 용도별 KOSIS 항목 목록 (투명성, `matrix.json` 그대로) |
| GET  | `/`               | -  | 서비스 안내 |

대화형 API 문서: 서버 실행 후 `http://127.0.0.1:8000/docs`

---

## 셋업 (Windows)

venv는 **풀경로**로 생성한다. Microsoft Store python은 쓰지 않는다.

```powershell
# 1) venv 생성 (정식 설치본 Python 3.11)
C:\Users\<you>\AppData\Local\Programs\Python\Python311\python.exe -m venv D:\APPS\arch-site-context\.venv

# 2) 의존성 설치
D:\APPS\arch-site-context\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3) 키 설정 (P1부터 필요)
copy .env.example .env   # 그리고 값 채우기

# 4) 서버 실행
.\scripts\run.ps1
# 또는: D:\APPS\arch-site-context\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## 테스트

```powershell
D:\APPS\arch-site-context\.venv\Scripts\python.exe -m pytest -q
```

---

## 배포 (GCP Cloud Run)

**단일 서비스** — 프론트(`frontend/dist`)를 백엔드가 정적 서빙한다. URL 하나, CORS 불필요, 배포·시크릿 한 번. (Dockerfile 멀티스테이지: node 로 프론트 빌드 → python 이미지에 복사)

키는 **이미지에 굽지 않고** Secret Manager → 런타임 env 주입. 캐시는 `GCS_CACHE_BUCKET` 지정 시 GCS, 아니면 로컬파일. 산출물(PNG)은 `OUT_DIR=/tmp/out`(Cloud Run 쓰기 가능 경로).

### 0. 준비 (1회)

```bash
gcloud config set project <PROJECT_ID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com storage.googleapis.com

# 캐시용 GCS 버킷
gcloud storage buckets create gs://<PROJECT_ID>-arch-cache --location=asia-northeast3
```

### 1. 시크릿 등록 (.env 값을 Secret Manager 로 — 커밋 금지)

```bash
for K in KAKAO_KEY VWORLD_KEY KOSIS_KEY ANTHROPIC_API_KEY JUSO_API_KEY; do
  printf "%s" "$(grep "^$K=" .env | cut -d= -f2-)" | \
    gcloud secrets create $K --data-file=- 2>/dev/null || \
  printf "%s" "$(grep "^$K=" .env | cut -d= -f2-)" | \
    gcloud secrets versions add $K --data-file=-
done
```

### 2. 배포

```bash
gcloud run deploy arch-site-context \
  --source . \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --memory 512Mi \
  --set-env-vars OUT_DIR=/tmp/out,GCS_CACHE_BUCKET=<PROJECT_ID>-arch-cache \
  --set-secrets KAKAO_KEY=KAKAO_KEY:latest,VWORLD_KEY=VWORLD_KEY:latest,KOSIS_KEY=KOSIS_KEY:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,JUSO_API_KEY=JUSO_API_KEY:latest
```

### 3. GCS 캐시 권한

배포 후 서비스 계정에 버킷 쓰기 권한:

```bash
SA=$(gcloud run services describe arch-site-context --region asia-northeast3 \
     --format='value(spec.template.spec.serviceAccountName)')
gcloud storage buckets add-iam-policy-binding gs://<PROJECT_ID>-arch-cache \
  --member="serviceAccount:$SA" --role=roles/storage.objectAdmin
```

### 4. VWorld 도메인 잠금 처리 (P2 방식)

VWorld 키가 도메인 잠금이면 둘 중 하나:
- **(권장)** VWorld 포털에서 배포된 Cloud Run URL 을 키의 **허용 도메인**에 등록, 또는
- 서비스 URL 을 `VWORLD_REFERER` env 로 주입(코드가 Referer 헤더로 전송 — `tiles.py`):
  ```bash
  gcloud run services update arch-site-context --region asia-northeast3 \
    --update-env-vars VWORLD_REFERER=https://<서비스-URL>
  ```
  (URL 은 1차 배포 후 확정되므로, 배포 → URL 확인 → 등록/주입 순서.)

### 5. 확인 (완료 기준)

배포 URL 접속 → [지역 통계] 표·문단 / [주변 시설] 목록·지도PNG 가 둘 다 끝까지 나오면 통과.

> JUSO 는 현재 **개발키**(개발서버 전용) — 운영에선 운영키 필요(DEFERRED D2). `EUM_*`·`DATA_GO_KR_API_KEY` 는 해당 기능 활성화 시 같은 방식으로 시크릿 추가.

---

P0 완료 기준: `uvicorn`으로 띄우고 `/health`와 `/facilities`가 샘플 JSON을 반환하면 통과.
