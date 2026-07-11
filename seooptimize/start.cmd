@echo off
REM SEOOptimize — launch the app and open the browser.
REM Usage from repo root:  start.cmd   or   .\start

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m app.cli start
) else (
    echo Virtual environment not found. Run: py -3.12 -m venv .venv ^&^& .venv\Scripts\pip install -e .
    exit /b 1
)
