# Starts the backend (FastAPI) on port 8000.
# On the first run it creates a virtual environment and installs everything.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot\backend

if (-not (Test-Path .\.venv)) {
    Write-Host 'Creating the virtual environment ...' -ForegroundColor Cyan
    python -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

if (-not (Test-Path .\.env)) {
    Write-Host 'Note: backend\.env is missing. Copy .env.example to .env to change any defaults.' -ForegroundColor Yellow
}

Write-Host 'Backend running on http://localhost:8000  (API docs: /docs)' -ForegroundColor Green
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
