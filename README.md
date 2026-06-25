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

P0 완료 기준: `uvicorn`으로 띄우고 `/health`와 `/facilities`가 샘플 JSON을 반환하면 통과.
