$ErrorActionPreference = "Stop"
try {
    $env:PYTHONPATH = $PSScriptRoot
    $venvPython = Join-Path $PSScriptRoot ".venv\Scripts\uvicorn.exe"
    if (-not (Test-Path $venvPython)) {
        throw "Virtual environment not found at .venv\Scripts\uvicorn.exe. Run build.bat first."
    }
    & $venvPython backend.main:app --reload --host 0.0.0.0 --port 8000 --log-level warning
} catch {
    Write-Error "Failed to start server: $_"
    exit 1
}