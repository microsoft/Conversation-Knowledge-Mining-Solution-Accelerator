#!/usr/bin/env pwsh

param(
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "ERROR: Missing virtual environment at .venv\Scripts\python.exe" -ForegroundColor Red
    Write-Host "Create the venv and install backend requirements first." -ForegroundColor Yellow
    exit 1
}

$listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listeners) {
    $owners = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($owner in $owners) {
        $taskkillOutput = & taskkill /PID $owner /T /F 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Stopped process on port $Port (PID $owner)" -ForegroundColor Yellow
        } else {
            Write-Host "Warning: could not stop PID $owner on port $Port" -ForegroundColor Yellow
        }
    }
}

$args = @("-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", "$Port")
if ($Reload) {
    $args += "--reload"
}

Write-Host "Starting backend on http://127.0.0.1:$Port" -ForegroundColor Green
if ($Reload) {
    Write-Host "Reload mode enabled. On Windows this can be less stable than the default single-process mode." -ForegroundColor Yellow
}

& $pythonExe @args