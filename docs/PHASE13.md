# Phase 13 Spec — Electron Packaging

**Branch:** `phase-13/electron-packaging`
**Depends on:** Phase 12 sealed (`145fd99`)
**Core principle:** Electron is a shell. It starts the Python backend and
displays the existing web cockpit. The Python backend is unchanged.

---

## Objective

Deliver a `.dmg` Mac installer that an operator double-clicks to install
Miktos. After install, they open the app from `/Applications`. No terminal,
no Python, no config files. The onboarding wizard runs on first launch.

---

## Architecture

```
Miktos.app (Electron)
  ├─ Electron main process (Node.js)
  │    ├─ Spawns Python server as child process
  │    ├─ Waits for server to be ready on port 8000
  │    ├─ Opens BrowserWindow → http://localhost:8000
  │    └─ Kills Python server on app quit
  └─ Resources/
       └─ miktos-server  ← PyInstaller-built Python executable

User data (outside app bundle, user-writable):
  ~/Library/Application Support/Miktos/
    .env                   ← credentials (written by onboarding wizard)
    config/
      session_config.yaml  ← session config
    data/                  ← sessions, messages, logs
    logs/
      server.log           ← uvicorn output
```

**Why this split:** macOS app bundles are read-only after signing.
User data (credentials, configs, session files) must live outside the bundle.
The Python server reads from `~/Library/Application Support/Miktos/` at runtime.

---

## Build Pipeline

```
Step 1: PyInstaller
  python scripts/build_server.py
  → bundles Python + all dependencies into dist/miktos-server (executable)
  → no Python installation required on the user's Mac

Step 2: electron-builder
  cd electron && npm run dist
  → copies dist/miktos-server into Electron app Resources/
  → packages into Miktos.app
  → creates Miktos-x.x.x.dmg
```

---

## File Structure

```
electron/
  main.js              ← Electron main process
  preload.js           ← minimal preload (contextIsolation)
  package.json         ← Electron + electron-builder config
  build/
    icon.icns          ← macOS app icon (1024x1024)
    icon.png           ← source icon
    entitlements.mac.plist  ← macOS entitlements for signing

scripts/
  build_server.py      ← NEW: runs PyInstaller to build miktos-server
  build_app.sh         ← NEW: full build pipeline (PyInstaller + electron-builder)

miktos.spec            ← NEW: PyInstaller spec file

docs/
  PHASE13.md           ← this spec
  INSTALL.md           ← NEW: operator installation guide
```

---

## `electron/main.js`

Core responsibilities:

```javascript
// 1. Resolve path to bundled Python server
const serverPath = app.isPackaged
  ? path.join(process.resourcesPath, 'miktos-server')
  : path.join(__dirname, '..', 'dist', 'miktos-server');

// 2. Resolve user data directory
const userDataDir = path.join(
  app.getPath('appData'), 'Miktos'
);
// Creates: ~/Library/Application Support/Miktos/

// 3. Spawn Python server
const server = spawn(serverPath, [], {
  env: { ...process.env, MIKTOS_DATA_DIR: userDataDir },
  stdio: ['ignore', logStream, logStream],
});

// 4. Wait for server ready (poll http://localhost:8000/api/onboarding/status)
async function waitForServer(maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      await fetch('http://localhost:8000/api/onboarding/status');
      return true; // server is up
    } catch {
      await sleep(500); // wait 500ms, try again
    }
  }
  return false; // timed out
}

// 5. Open BrowserWindow
const win = new BrowserWindow({
  width: 1280,
  height: 800,
  title: 'Miktos',
  webPreferences: {
    preload: path.join(__dirname, 'preload.js'),
    contextIsolation: true,
  },
});
win.loadURL('http://localhost:8000');

// 6. Kill server on quit
app.on('before-quit', () => {
  if (server && !server.killed) server.kill('SIGTERM');
});
```

**Loading screen:** While waiting for the server, show a native loading
window with the Miktos logo. Replace it with the cockpit once ready.

**Menu bar icon:** `Tray` icon showing M (Miktos). Click opens the main
window. Quit option in tray menu.

---

## `miktos.spec` — PyInstaller Spec

```python
# miktos.spec
block_cipher = None

a = Analysis(
    ['miktos_entry.py'],       # NEW entry point (see below)
    pathex=['.'],
    binaries=[],
    datas=[
        ('web/templates', 'web/templates'),
        ('web/static', 'web/static'),
        ('domains', 'domains'),
        ('engine', 'engine'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.main',
        'fastapi',
        'jinja2',
        'google.auth',
        'google.oauth2',
        'google_auth_oauthlib',
    ],
    ...
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='miktos-server',
    console=False,  # no terminal window on macOS
    ...
)
```

**`miktos_entry.py`** — new file, PyInstaller entry point:

```python
"""PyInstaller entry point for the Miktos server."""
import os
import uvicorn
from pathlib import Path

# Resolve user data directory (passed by Electron via env var)
data_dir = Path(os.environ.get('MIKTOS_DATA_DIR',
    Path.home() / 'Library' / 'Application Support' / 'Miktos'
))
data_dir.mkdir(parents=True, exist_ok=True)

# Set env vars so the rest of the app finds user data
os.environ['MIKTOS_DATA_DIR'] = str(data_dir)

if __name__ == '__main__':
    uvicorn.run(
        'web.server:app',
        host='127.0.0.1',
        port=8000,
        reload=False,  # no reload in production
        log_level='info',
    )
```

---

## User Data Migration

The Python backend currently reads/writes paths relative to the project root.
In the packaged app, user data moves to `~/Library/Application Support/Miktos/`.

**Files that move:**

| Current path | Packaged path |
|---|---|
| `.env` | `~/Library/Application Support/Miktos/.env` |
| `domains/streamlab_post/config/session_config.yaml` | `~/Library/Application Support/Miktos/config/session_config.yaml` |
| `data/` | `~/Library/Application Support/Miktos/data/` |

**Implementation:** Add a `paths.py` module that resolves all user data
paths based on `MIKTOS_DATA_DIR` env var:

```python
# engine/paths.py
import os
from pathlib import Path

def get_data_dir() -> Path:
    """Returns the user data directory.
    Development: project root / data
    Packaged:    ~/Library/Application Support/Miktos/data
    """
    env = os.environ.get('MIKTOS_DATA_DIR')
    if env:
        return Path(env) / 'data'
    return Path(__file__).parent.parent / 'data'

def get_config_dir() -> Path:
    env = os.environ.get('MIKTOS_DATA_DIR')
    if env:
        return Path(env) / 'config'
    return Path(__file__).parent.parent / 'domains/streamlab_post/config'

def get_env_path() -> Path:
    env = os.environ.get('MIKTOS_DATA_DIR')
    if env:
        return Path(env) / '.env'
    return Path(__file__).parent.parent / '.env'
```

All path references in `web/`, `domains/`, and `scripts/` migrate to use
`get_data_dir()`, `get_config_dir()`, `get_env_path()`.

In development (no `MIKTOS_DATA_DIR`): behaves exactly as today.
In packaged app: reads/writes to the Application Support directory.

**This is the most impactful code change in Phase 13.**

---

## Python Version Note

PyInstaller 6.x supports Python up to 3.13. Python 3.14 (current dev
environment) support may not be available yet.

**Recommendation:** Build the packaged version using Python 3.12 or 3.13.
Development can continue on 3.14. The build script creates a separate
venv with Python 3.12 for the PyInstaller build step.

Check PyInstaller compatibility before starting the build:
```bash
.venv/bin/python -c "import sys; print(sys.version)"
pip index versions pyinstaller
```

---

## `electron/package.json`

```json
{
  "name": "miktos",
  "version": "0.1.0",
  "description": "Miktos — Bilingual Live Stream Production System",
  "main": "main.js",
  "scripts": {
    "start": "electron .",
    "dist": "electron-builder --mac"
  },
  "dependencies": {
    "electron": "^30.0.0"
  },
  "devDependencies": {
    "electron-builder": "^24.0.0"
  },
  "build": {
    "appId": "com.miktos.app",
    "productName": "Miktos",
    "mac": {
      "target": "dmg",
      "icon": "build/icon.icns",
      "category": "public.app-category.video"
    },
    "extraResources": [
      {
        "from": "../dist/miktos-server",
        "to": "miktos-server"
      }
    ],
    "dmg": {
      "title": "Miktos Installer",
      "background": "build/dmg-background.png"
    }
  }
}
```

---

## First Launch Experience

1. User double-clicks `Miktos.dmg`, drags to Applications
2. Opens Miktos from Applications
3. Loading screen appears (Miktos logo, “Starting…”)
4. Python server starts in background (~3-5 seconds)
5. Loading screen replaced by the web cockpit
6. If credentials missing: onboarding wizard banner visible
7. Operator completes wizard → ready to stream

On subsequent launches:
- Steps 1-5 only
- Cockpit opens directly, no wizard banner

---

## Tests

No new Python tests for Phase 13 — the Python backend is unchanged.
Existing 140 tests still run and pass.

**Manual validation checklist:**

- [ ] `python scripts/build_server.py` completes without error
- [ ] `dist/miktos-server` runs standalone (no Python needed): `./dist/miktos-server`
  - Server starts, `http://localhost:8000` responds
- [ ] `cd electron && npm run dist` produces `Miktos.dmg`
- [ ] Install `.dmg`: drag to Applications, open
- [ ] Loading screen appears, then cockpit appears
- [ ] `/onboarding/status` shows correct credential state
- [ ] Start Session button works
- [ ] Quit Miktos → Python server stops (no orphan process)
- [ ] Reopen Miktos → server starts fresh
- [ ] User data written to `~/Library/Application Support/Miktos/`

---

## What Does Not Change

- `web/server.py` — unchanged except port managed via env var if needed
- All API endpoints — unchanged
- All 140 tests — pass unmodified in development
- Onboarding wizard — works identically in packaged app
- Pearl and OBS integrations — unchanged
- `run_session.py` terminal path — preserved as fallback

---

## Seal Criteria

- `Miktos.dmg` installs and opens without a terminal
- First launch shows loading screen then cockpit
- Onboarding wizard completes and writes credentials to
  `~/Library/Application Support/Miktos/.env`
- Start Session works from inside the packaged app
- Python server stops cleanly when app is quit
- 140 Python tests still pass in development environment

---

## Non-Goals for Phase 13

- **Code signing and notarization** — required for distribution outside
  direct download, but not for Phase 13 local validation. Add in Phase 13b.
- **Auto-update** — Squirrel.mac or electron-updater. Phase 13b.
- **Windows build** — requires path audit. Phase 13c if needed.
- **App Store distribution** — requires sandboxing changes. Future.

---

*Spec written 2026-04-30.*
*Branch: `phase-13/electron-packaging` from `main` at `145fd99`.*
