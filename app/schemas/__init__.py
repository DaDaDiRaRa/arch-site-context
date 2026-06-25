"""Pydantic v2 데이터 계약 (CLAUDE.md 6장).

스키마는 코드보다 먼저 확정된다. 여기 정의가 모든 엔드포인트의 입출력 계약.
"""

from .facility import FacilityRequest, FacilityResult, MapRequest
from .region import AnalyzeRequest, RegionStat
from .diagnose import DiagnoseRequest, DiagnoseResult
from .compare import CompareRequest, CompareResult
from .ask import AskRequest, AskResult
from .errors import ErrorBlock

__all__ = [
    "FacilityRequest",
    "FacilityResult",
    "MapRequest",
    "AnalyzeRequest",
    "RegionStat",
    "DiagnoseRequest",
    "DiagnoseResult",
    "CompareRequest",
    "CompareResult",
    "AskRequest",
    "AskResult",
    "ErrorBlock",
]
