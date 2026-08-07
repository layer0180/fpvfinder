# Starts the frontend (Vite) on port 5173.
# The backend has to be running alongside it (start-backend.ps1).

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot\frontend

if (-not (Test-Path .\node_modules)) {
    Write-Host 'Installing npm packages ...' -ForegroundColor Cyan
    npm install
}

Write-Host 'Frontend running on http://localhost:5173' -ForegroundColor Green
npm run dev
