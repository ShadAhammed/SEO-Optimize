"""SEOOptimize repository CLI.

Usage (from repo root, with venv activated after ``pip install -e .``):

    start          Launch the app and open the browser
    Start          Same (case-insensitive on Windows)

Or without installing:

    .\\start.ps1
    .\\start.cmd
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_URL = "http://localhost:8501"
DEFAULT_PORT = 8501


def _venv_streamlit() -> Path | None:
    """Return path to the venv streamlit executable, if it exists."""
    if sys.platform == "win32":
        candidate = REPO_ROOT / ".venv" / "Scripts" / "streamlit.exe"
    else:
        candidate = REPO_ROOT / ".venv" / "bin" / "streamlit"
    return candidate if candidate.exists() else None


def _streamlit_command() -> list[str]:
    """Build the streamlit launch command."""
    venv_bin = _venv_streamlit()
    if venv_bin:
        return [str(venv_bin), "run", "app/main.py"]
    return [sys.executable, "-m", "streamlit", "run", "app/main.py"]


def start() -> int:
    """Launch Streamlit and open the default browser tab."""
    if not (REPO_ROOT / "app" / "main.py").exists():
        print("Error: run this command from the seooptimize repository root.", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env.setdefault("BROWSER", "default")

    cmd = _streamlit_command() + [
        f"--server.port={DEFAULT_PORT}",
        "--server.headless=false",
        "--browser.serverAddress=localhost",
        f"--browser.serverPort={DEFAULT_PORT}",
    ]

    print("Starting SEOOptimize…")
    print(f"  URL: {DEFAULT_URL}")
    print("  Press Ctrl+C to stop.\n")

    try:
        return subprocess.call(cmd, cwd=REPO_ROOT, env=env)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def main() -> None:
    """Entry point for ``python -m app.cli``."""
    raise SystemExit(start())


if __name__ == "__main__":
    main()
