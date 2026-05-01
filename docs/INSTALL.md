# Miktos — Installation Guide

## System Requirements

| Requirement | Minimum |
|---|---|
| macOS | 13 Ventura or later |
| Architecture | Apple Silicon (arm64) or Intel (x64) |
| Disk space | 500 MB |
| RAM | 4 GB |

---

## Operator Installation (End-User)

1. **Download** `Miktos-0.1.0.dmg` from the releases page.
2. **Open** the `.dmg` and drag `Miktos.app` to your **Applications** folder.
3. **Launch** Miktos from Launchpad or Spotlight (`⌘ Space → Miktos`).
4. On first launch, macOS may show a Gatekeeper warning. Click **Open Anyway** in  
   **System Settings → Privacy & Security**.
5. The **Onboarding Wizard** opens automatically and guides you through entering:
   - YouTube Client ID and Client Secret
   - Google Translate API key
   - ElevenLabs API key
   - YouTube OAuth tokens (via in-app browser flow)

### User Data Location

All credentials and session data are stored in:

```
~/Library/Application Support/Miktos/
├── .env                          # API credentials (never shared)
├── config/
│   └── session_config.yaml       # Stream session configuration
└── data/
    ├── sessions/                 # Past session records
    ├── logs/                     # Layout event logs
    ├── state/                    # Run-state snapshots
    └── messages/                 # Inter-agent message queues
```

---

## Developer Build

### Prerequisites

- **Python 3.13** — `brew install python@3.13`
- **Node.js 20+** — `brew install node`
- **Python 3.14** dev venv (for tests) — already set up at `.venv/`

### Build the Server Binary

```bash
python3.13 scripts/build_server.py
```

This creates `.venv-build/` (Python 3.13 venv) and outputs `dist/miktos-server`.

### Verify the Server Binary

```bash
./dist/miktos-server
# → Uvicorn running on http://127.0.0.1:8000
```

Open `http://localhost:8000` in your browser to confirm the UI loads.

### Build the macOS App

```bash
bash scripts/build_app.sh
```

This runs PyInstaller then `electron-builder`, producing:

```
electron/dist/Miktos-0.1.0.dmg
```

### Run in Dev Mode (Electron + live server)

```bash
# Terminal 1 — run the Python server
.venv/bin/uvicorn web.server:app --reload

# Terminal 2 — run Electron pointing to dev server
cd electron && npm start
```

---

## Troubleshooting

| Symptom | Resolution |
|---|---|
| `miktos-server not found` | Run `python3.13 scripts/build_server.py` |
| Server does not start | Check Console.app for crash logs; ensure port 8000 is free |
| "App is damaged" Gatekeeper error | `xattr -cr /Applications/Miktos.app` |
| Credentials not saved | Check `~/Library/Application Support/Miktos/.env` permissions |
| Onboarding wizard loops | Delete `.env` in the Miktos data directory and restart |

---

## Uninstall

1. Drag `Miktos.app` from Applications to Trash.
2. Optionally remove user data:
   ```bash
   rm -rf ~/Library/Application\ Support/Miktos
   ```
