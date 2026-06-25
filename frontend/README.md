# 터읽기 프론트엔드 (React + Vite + Tailwind)

백엔드(FastAPI)에 붙는 단일 화면. 주소 입력 1개 + 탭 2개.

- **지역 통계(A)**: 용도 선택 → `/analyze` → facts 표 + 참고 시사점 + 한 문단(복사). '○○구 기준'·연도·source 배지.
- **주변 시설(B)**: 시설 종류·반경 선택 → `/facilities` 개수표·목록 → `/facilities/map` 위성 PNG 미리보기·다운로드.

## 실행

```bash
# 1) 백엔드 먼저 (프로젝트 루트)
.\scripts\run.ps1        # http://127.0.0.1:8000

# 2) 프론트
cd frontend
npm install
npm run dev              # http://localhost:5173
```

개발 서버는 Vite 프록시로 `/analyze`·`/facilities`·`/files` 등을 백엔드(8000)로 넘긴다 (CORS 불필요).
백엔드 주소가 다르면 `VITE_API_TARGET` 환경변수로 지정:

```bash
VITE_API_TARGET=http://localhost:8001 npm run dev
```

## 빌드

```bash
npm run build           # dist/ 정적 파일
```
