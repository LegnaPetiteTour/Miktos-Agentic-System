"""scripts/build_server.py — Build the miktos-server standalone binary.

Uses Python 3.13 (not the dev 3.14 venv) because PyInstaller has full
support for 3.13 but may have issues with 3.14.

Workflow:
  1. Locate Python 3.13 executable.
  2. Create .venv-build/ if it does not exist.
  3. Install all production dependencies + pyinstaller into .venv-build/.
  4. Run: pyinstaller miktos.spec --clean --distpath dist/
  5. Report the output binary path.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
BUILD_VENV = REPO_ROOT / ".venv-build"
PYTHON_313_CANDIDATES = [
    "/opt/homebrew/bin/python3.13",
    "/usr/local/bin/python3.13",
    "/usr/bin/python3.13",
    "python3.13",
]


def _find_python313() -> str:
    """Return path to Python 3.13 or abort."""
    for candidate in PYTHON_313_CANDIDATES:
        found = shutil.which(candidate) or (
            Path(candidate).exists() and candidate or None
        )
        if found:
            return found
    sys.exit(
        "ERROR: Python 3.13 not found. Install it (e.g. brew install python@3.13) "
        "and ensure it is on PATH or at /opt/homebrew/bin/python3.13."
    )


def _run(cmd: list[str], **kwargs) -> None:
    """Run a command, streaming output, abort on failure."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        sys.exit(f"Command failed with exit code {result.returncode}")


def main() -> None:
    print("=== Miktos server build ===")
    print(f"Repo root: {REPO_ROOT}")

    # 1. Find Python 3.13
    py313 = _find_python313()
    print(f"Python 3.13: {py313}")

    # 2. Create build venv if needed
    venv_python = BUILD_VENV / "bin" / "python"
    venv_pip = BUILD_VENV / "bin" / "pip"

    if not venv_python.exists():
        print(f"\nCreating build venv at {BUILD_VENV} ...")
        _run([py313, "-m", "venv", str(BUILD_VENV)])
    else:
        print(f"\nBuild venv exists: {BUILD_VENV}")

    # 3. Upgrade pip and install production deps + PyInstaller
    print("\nInstalling dependencies into build venv ...")
    _run([str(venv_pip), "install", "--upgrade", "pip"], cwd=REPO_ROOT)
    _run(
        [
            str(venv_pip),
            "install",
            "--upgrade",
            "pyinstaller",
            # Production deps from pyproject.toml
            "langgraph>=0.2.0",
            "pydantic>=2.0.0",
            "python-dotenv>=1.0.0",
            "pyyaml>=6.0",
            "typing-extensions>=4.0.0",
            "Pillow>=10.0.0",
            "piexif>=1.1.3",
            "obsws-python>=1.7.0",
            "google-api-python-client>=2.0",
            "google-auth-httplib2>=0.2",
            "google-auth-oauthlib>=1.0",
            "requests>=2.31",
            "msal>=1.24",
            "psutil>=5.9",
            "rich>=13.0",
            "fastapi>=0.111",
            "uvicorn[standard]>=0.29",
            "jinja2>=3.1",
            "python-multipart>=0.0.9",
        ],
        cwd=REPO_ROOT,
    )

    # 4. Run PyInstaller
    pyinstaller_bin = BUILD_VENV / "bin" / "pyinstaller"
    print("\nRunning PyInstaller ...")
    _run(
        [
            str(pyinstaller_bin),
            "miktos.spec",
            "--clean",
            "--distpath",
            "dist",
            "--workpath",
            "build",
            "--noconfirm",
        ],
        cwd=REPO_ROOT,
    )

    # 5. Report
    binary = REPO_ROOT / "dist" / "miktos-server"
    if binary.exists():
        size_mb = binary.stat().st_size / (1024 * 1024)
        print(f"\n✓ Build complete: {binary}  ({size_mb:.1f} MB)")
    else:
        sys.exit(f"\nERROR: Expected binary not found at {binary}")


if __name__ == "__main__":
    main()
