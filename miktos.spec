# miktos.spec — PyInstaller build spec for miktos-server
# Run with: pyinstaller miktos.spec --clean
#
# Uses the Python 3.13 build venv (not the dev venv) to avoid
# PyInstaller compatibility issues with Python 3.14.
# ruff: noqa: F821  — Analysis, PYZ, EXE are PyInstaller DSL globals

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ---------------------------------------------------------------------------
# Hidden imports — packages that use dynamic imports or plugins
# ---------------------------------------------------------------------------
hidden_imports = [
    # uvicorn
    *collect_submodules("uvicorn"),
    # fastapi
    "fastapi",
    "fastapi.responses",
    "fastapi.staticfiles",
    "fastapi.templating",
    "fastapi.middleware.cors",
    # starlette (fastapi's underlying framework)
    *collect_submodules("starlette"),
    # jinja2
    "jinja2",
    "jinja2.ext",
    # pydantic
    *collect_submodules("pydantic"),
    # python-dotenv
    "dotenv",
    # pyyaml
    "yaml",
    # google auth
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google.oauth2",
    "google.oauth2.credentials",
    "google_auth_oauthlib",
    "google_auth_oauthlib.flow",
    # httplib2
    "httplib2",
    # requests
    "requests",
    # multipart
    "multipart",
    # msal
    "msal",
    # anyio (uvicorn async backend)
    *collect_submodules("anyio"),
    # h11 (uvicorn HTTP/1.1)
    "h11",
    # click (uvicorn CLI)
    "click",
]

# ---------------------------------------------------------------------------
# Data files — templates, static assets, and bundled configs
# ---------------------------------------------------------------------------
datas = [
    # Web templates and static files
    ("web/templates", "web/templates"),
    ("web/static", "web/static"),
    # Domain python packages (needed for relative imports at runtime)
    ("domains", "domains"),
    # Engine (already included via source, but include non-py assets)
    ("engine", "engine"),
]

# Collect data files from uvicorn (it ships .html error pages)
datas += collect_data_files("uvicorn")

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["miktos_entry.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude dev / test tools
        "pytest",
        "ruff",
        "mypy",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="miktos-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # keep console visible for operator debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
