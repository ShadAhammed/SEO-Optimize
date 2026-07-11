# SEOOptimize — launch the Streamlit app and open the browser.
# Usage from repo root:  .\start   or   .\Start

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

$Cli = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Cli)) {
    Write-Host "Virtual environment not found. Creating and installing…" -ForegroundColor Yellow
    py -3.12 -m venv .venv
    & (Join-Path $Root ".venv\Scripts\python.exe") -m pip install -q -e .
}

& $Cli -m app.cli start
