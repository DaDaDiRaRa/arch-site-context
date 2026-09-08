# ── Stage 1: 프론트 빌드 (React+Vite) ───────────────────────
FROM node:22-slim AS frontend
WORKDIR /fe
ARG VITE_CONCEPT_STUDIO_URL=https://concept-studio-dqj4exlefq-du.a.run.app
ENV VITE_CONCEPT_STUDIO_URL=${VITE_CONCEPT_STUDIO_URL}
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # → /fe/dist

# kordoc CLI (§8.15 HWP 내보내기 — POST /board/hwp 의 markdownToHwpx). concept-studio 가
# 검증한 버전으로 고정(services/kordoc_client.py TESTED_VERSION) — latest 는 그 검증 밖.
# OCR/PDF 전용 무거운 선택적 의존성(sharp·onnxruntime 등)은 우리가 안 쓰므로 --omit=optional.
WORKDIR /kordoc
RUN npm init -y >/dev/null \
    && npm install kordoc@3.4.1 --omit=optional --no-fund --no-audit

# ── Stage 2: 백엔드 (FastAPI + 프론트 정적 서빙) ─────────────
FROM python:3.11-slim
WORKDIR /app

# 한글 폰트(PIL 위성 PNG 라벨 — 없으면 한글 두부 깨짐, map_compose._font)
# + Node.js 런타임(kordoc CLI 실행용, §8.15 — apt 가 의존 라이브러리까지 같이 해결)
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-nanum nodejs \
    && rm -rf /var/lib/apt/lists/*

# 의존성 먼저 (레이어 캐시)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 백엔드 코드 + 데이터(JSON)
COPY app/ ./app/

# MCP 서버(/mcp 로 app/main.py 가 마운트) — app/ 이 직접 import 하므로 같이 넣는다.
COPY mcp_server/ ./mcp_server/

# 빌드된 프론트를 백엔드가 정적 서빙할 위치로 복사 (단일 서비스)
COPY --from=frontend /fe/dist ./frontend/dist

# kordoc(§8.15 HWP 내보내기) — 설치된 패키지만 복사 (런타임은 위 apt nodejs 사용).
# services/kordoc_client.py 가 KORDOC_CLI(.js 경로)를 보면 `node <경로>` 로 실행한다.
COPY --from=frontend /kordoc/node_modules ./kordoc/node_modules
ENV KORDOC_CLI=/app/kordoc/node_modules/kordoc/dist/cli.js

# Cloud Run: 컨테이너 FS 는 임시 → 쓰기 가능한 경로로 산출물/캐시 지정
ENV OUT_DIR=/tmp/out
ENV PORT=8080

# Cloud Run 이 주입하는 $PORT 에 바인딩 (shell 형식이라야 변수 확장)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
