"""공용 픽스처.

B4: /board 결과 캐시(_BOARD_CACHE)는 프로세스 전역이라 테스트 간 결과가 샐 수 있다
(같은 주소·용도를 여러 테스트가 서로 다른 monkeypatch 로 재사용). 각 테스트 전에 비워
격리를 보장한다. 운영에는 영향 없음(테스트 전용).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_board_cache():
    from app.routers import board as _board
    _board._BOARD_CACHE.clear()
    yield
    _board._BOARD_CACHE.clear()
