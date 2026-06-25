# 로컬 개발 서버 실행 (Windows PowerShell)
# venv는 풀경로 .venv 사용. uvicorn으로 app.main:app 띄움.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Error "venv가 없습니다. README의 셋업 절차로 .venv를 먼저 생성하세요."
    exit 1
}

& $py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
