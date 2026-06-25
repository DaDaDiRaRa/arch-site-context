# ── Stage 1: 프론트 빌드 (React+Vite) ───────────────────────
FROM node:22-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # → /fe/dist

# ── Stage 2: 백엔드 (FastAPI + 프론트 정적 서빙) ─────────────
FROM python:3.11-slim
WORKDIR /app

# 의존성 먼저 (레이어 캐시)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 백엔드 코드 + 데이터(JSON)
COPY app/ ./app/

# 빌드된 프론트를 백엔드가 정적 서빙할 위치로 복사 (단일 서비스)
COPY --from=frontend /fe/dist ./frontend/dist

# Cloud Run: 컨테이너 FS 는 임시 → 쓰기 가능한 경로로 산출물/캐시 지정
ENV OUT_DIR=/tmp/out
ENV PORT=8080

# Cloud Run 이 주입하는 $PORT 에 바인딩 (shell 형식이라야 변수 확장)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
