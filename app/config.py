"""런타임 경로 설정 (로컬/Cloud Run 공용).

OUT_DIR: 합성 PNG·캐시 등 런타임 생성물 위치. Cloud Run 은 컨테이너 FS 가 임시이므로
         /tmp 등 쓰기 가능한 경로를 OUT_DIR 로 지정 (배포 env).
FRONTEND_DIST: 빌드된 프론트(dist). 있으면 백엔드가 정적 서빙 (단일 서비스).
"""

from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

OUT_DIR = Path(os.getenv("OUT_DIR", str(_ROOT / "out")))
FRONTEND_DIST = _ROOT / "frontend" / "dist"
