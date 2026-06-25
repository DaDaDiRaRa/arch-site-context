# DEFERRED — 보류·나중에 확인할 것

> 단계별로 진행하다 **보류했거나 사람이 확인/결정해야 할 것**을 여기 모은다.
> 사용자가 "그때 물어볼게" 한 항목들. 새 Phase에서 생기면 계속 추가한다.
> 상세 기술 메모는 CLAUDE.md(§8.5 공공데이터, §8.6 KOSIS)에 있고, 여기는 **할 일 목록** 중심.

마지막 업데이트: 2026-06-25 (P5까지)

---

## 🔴 사람이 액션해야 풀리는 것 (블로커)

### D1. 공공데이터포털 키 미등록 (경로당 보강, P1.5b)
- **증상**: `DATA_GO_KR_API_KEY` 로 호출 시 `code 30 (SERVICE KEY IS NOT REGISTERED)`.
- **원인 후보**: ① 데이터셋 활용신청 미승인 ② 신규 키 전파 지연(1~2h) ③ 키 일부만 복사(현재 64자 hex).
- **할 일(사용자)**: data.go.kr 로그인 → 마이페이지 활용신청 현황 확인 → [전국마을회관및경로당표준데이터(15114136)](https://www.data.go.kr/data/15114136/standard.do) 활용신청 → 승인 후 1~2h.
- **확인법**: `.venv\Scripts\python.exe scripts\check_dataportal.py` (아래 D-스크립트) 가 resultCode 00 이면 OK.
- **풀리면**: 엔드포인트·필드 이미 확정(CLAUDE.md §8.5). 끼우는 작업 가벼움.

### D2. JUSO 운영키 (배포 전, P8)
- **증상**: 현재 `JUSO_API_KEY` 는 `dev` 키 → 개발서버(business.juso.go.kr) 전용.
- **할 일(사용자)**: 운영 배포 전 juso.go.kr 에서 **운영키** 발급 → .env 교체.
- **영향**: 로컬·개발은 지금 키로 OK. Cloud Run(P8) 배포 시에만 필요.

### D3. VWorld 키 도메인 잠금 여부 (배포 전, P8)
- **현황**: 로컬에선 Referer 없이 통과(잠금 아님). 배포 도메인에서도 되는지는 배포 후 확인.
- **할 일**: 배포 후 위성 타일 안 나오면 .env 에 `VWORLD_REFERER` 설정하거나 카카오 스카이뷰 폴백(자리 마련됨).

---

## 🟡 데이터 확정 필요 (코드 변경 없이 JSON만 채우면 됨)

### D4. KOSIS 미확정 지표 (P5, §8.6)
matrix.json 에서 `method:"unconfirmed"` 인 지표들 — 추정 않고 건너뛰는 중. 각 KOSIS (orgId/tblId/itmId) 확정되면 matrix.json 에 채우면 끝.
- 1인가구비율, 평균가구원수 (인구주택총조사)
- 인구밀도 (면적 결합 필요)
- 사업체수, 종사자수 (전국사업체조사)
- 주택보급률, 주간인구지수
- **메모**: KOSIS 메타 API 는 포맷이 달라 막힘 → 데이터 응답(itmId=ALL,objL=ALL)에서 코드 역추출하는 방식으로 확정.

### D5. matrix.json / implications.json 내용 검수 (건축가)
- 현재 항목·우선순위·함의 규칙은 **골격(예시)**. 건축가가 실제 설계 관점에서 검수·보강 필요.
- 코드 수정 없이 JSON 만 고치면 반영됨 (절대 원칙 7).

---

## 🟢 제품 방향 결정 (사용자 판단)

### D6. 토지이음(EUM) 규제정보 포함 여부
- `EUM_ID`/`EUM_KEY` 보유. 용도지역·행위제한 = **규제 정보**.
- **긴장**: CLAUDE.md 포지셔닝은 "인문·생활 맥락"이고 규제는 닥터빌드/Forma 트랙. 정체성 결정 필요.
- **미검증**: EUM API 엔드포인트/스펙 아직 실호출 안 함. 진행 결정 시 먼저 검증.
- 자세한 분석은 대화 기록 참고. 결정 보류 중.

---

## 🔧 기술 부채 / 나중에 손볼 것

### D7. 스타라이트 TestClient httpx Deprecation 경고
- 테스트 실행 시 `StarletteDeprecationWarning: install httpx2`. 기능 영향 없음. 의존성 정리 때 처리.

### D8. KOSIS 캐시 무효화 정책 없음
- 현재 FileCache 는 만료(TTL) 없음. 통계는 연 1회 갱신이라 당장 문제 없으나, 배포 시 GCS 캐시 + 갱신주기(연 1회) 고려.

### D9. 프론트 운영 서빙 (P8 배포 때)
- 현재는 dev: Vite 프록시로 백엔드(8000) 연결. 운영은 `npm run build` → `dist/` 를 FastAPI StaticFiles 로 서빙하거나 별도 호스팅 + 백엔드 CORS 설정 필요.
- dev 포트: 5173 점유 시 Vite 가 자동으로 다음 포트(5174…)로 띄움. 터미널에 찍힌 실제 URL 사용.

---

## 확인용 스크립트 (사용자가 직접 돌려볼 수 있는 것)
- `scripts/check_vworld_tile.py` — VWorld 위성타일 수신 게이트 (P2, ✅통과).
- `scripts/check_dataportal.py` — 공공데이터포털 키 등록 확인 (D1용). resultCode 00 이면 등록 완료.
