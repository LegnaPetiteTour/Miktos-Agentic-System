# Phase 12 Spec — Operator Onboarding Wizard

**Branch:** `phase-12/onboarding-wizard`
**Depends on:** Phase 11 sealed (`18c0f07`)
**Core principle:** The wizard automates what the operator currently does
by hand. No new credential mechanism — everything still reads from `.env`.
The wizard just writes `.env` correctly without the operator touching a terminal.

---

## Why This Phase Exists

Currently a new operator must:
1. Copy `.env.example` to `.env` manually
2. Create Google Cloud credentials in a browser, copy IDs into `.env`
3. Run `python scripts/youtube_auth.py --channel en` from a terminal,
   follow the OAuth flow, manually copy the printed token back into `.env`
4. Repeat step 3 for FR
5. Obtain an ElevenLabs API key, paste it into `.env`
6. Obtain a Google Translate API key, paste it into `.env`
7. Know the Pearl IP address or OBS WebSocket settings

None of this is acceptable for a non-technical operator.
Phase 12 replaces all of it with a browser-based wizard.

---

## What Changes

### New route: `/onboarding`

The web cockpit gains a dedicated onboarding view. When the server starts,
it checks whether required credentials exist in `.env`. If any are missing,
the cockpit shows a banner linking to `/onboarding`. The operator can also
reach it from the nav at any time.

The wizard has five steps, each on its own page within `/onboarding`:
1. **YouTube credentials** — Client ID + Secret entry, then OAuth flow for EN and FR
2. **Google Translate** — API key entry + live validation
3. **ElevenLabs** — API key entry + live validation
4. **Hardware** — Pearl IP or OBS host/port/password + connection test
5. **Ready** — summary of all checks, green when complete

### Credential storage

All credentials are written to `.env` in the project root.
This is what the rest of the system already reads. No new mechanism.

The wizard uses a `write_env_key(key, value)` helper that:
- Reads the current `.env`
- Updates or appends the key-value pair
- Writes the file back
- Never removes keys that are not being updated

### YouTube OAuth flow (in-browser, no terminal)

The current `youtube_auth.py` runs `InstalledAppFlow.run_local_server()`
which opens a browser and handles the redirect locally. Phase 12 moves
this flow into FastAPI:

```
GET  /onboarding/youtube/authorize?channel=en
     → Redirects to Google OAuth consent screen
     → Google redirects back to /onboarding/youtube/callback?code=...&state=en

GET  /onboarding/youtube/callback
     → Exchanges code for refresh token
     → Writes YOUTUBE_REFRESH_TOKEN_EN (or _FR) to .env
     → Redirects to /onboarding with success state
```

The operator clicks "Authorize EN Channel" in the browser. Google's consent
screen opens in the same tab. After approval, they land back in the Miktos
onboarding page with a green checkmark. No token is ever shown or copied.

### Validation endpoints

```
POST /api/onboarding/validate/translate
     Body: {api_key: str}
     → Makes a minimal Google Translate API call
     → Returns {success: bool, error: str|null}
     → Writes GOOGLE_TRANSLATE_API_KEY to .env on success

POST /api/onboarding/validate/elevenlabs
     Body: {api_key: str}
     → Calls ElevenLabs GET /v1/user endpoint
     → Returns {success: bool, error: str|null}
     → Writes ELEVENLABS_API_KEY to .env on success

POST /api/onboarding/validate/pearl
     Body: {host: str, port: int}
     → Calls GET http://{host}:{port}/api/channels
     → Returns {success: bool, firmware: str|null, error: str|null}
     → Writes pearl config to session_config.yaml on success

POST /api/onboarding/validate/obs
     Body: {host: str, port: int, password: str}
     → Attempts OBS WebSocket connection
     → Returns {success: bool, version: str|null, error: str|null}
     → Writes OBS config to session_config.yaml on success

GET  /api/onboarding/status
     → Returns current credential status for all required keys
     → {youtube_client: bool, youtube_en: bool, youtube_fr: bool,
        translate: bool, elevenlabs: bool, hardware: str|null}
```

---

## File Structure

```
web/
  api/
    onboarding.py        ← NEW — all onboarding endpoints
  templates/
    onboarding.html      ← NEW — wizard shell (steps nav + content area)
    onboarding_youtube.html   ← step 1
    onboarding_translate.html ← step 2
    onboarding_elevenlabs.html ← step 3
    onboarding_hardware.html  ← step 4
    onboarding_ready.html     ← step 5
  server.py              ← MODIFIED — include onboarding router,
                                      add startup credential check
tests/
  test_phase_12_onboarding.py  ← NEW — ~10 tests
```

---

## `web/api/onboarding.py`

New module. Responsibilities:
- `write_env_key(key, value)` — safe `.env` writer
- `read_env_keys()` — reads current `.env` state for status endpoint
- YouTube OAuth initiation + callback handlers
- Validation endpoints for each credential type
- Status endpoint

The OAuth flow uses `google-auth-oauthlib` (already a dependency via `youtube_auth.py`).
The FastAPI redirect URI is `http://localhost:8000/onboarding/youtube/callback`.

---

## Startup credential check

`web/server.py` calls `check_credentials()` on startup and stores the result
in app state. The index route (`/`) includes a `missing_credentials: bool`
flag in the template context. If `True`, the cockpit shows:

```
⚠️  Setup incomplete — some credentials are missing.
    Complete setup →
```

This banner disappears once all required credentials are present.
It does not block the operator from using the cockpit — it is informational.

---

## `.env` writer safety rules

1. Read the current `.env` into memory first
2. Parse line by line, preserving comments and blank lines
3. If the key exists: replace that line only
4. If the key does not exist: append at the end
5. Write atomically (write to temp file, rename)
6. Never delete or modify keys that are not being updated
7. Never log or return the value to the browser (write-only)

---

## What the operator sees (happy path)

1. Opens `http://localhost:8000` for the first time
2. Sees the banner: “Setup incomplete — Complete setup →”
3. Clicks the link, arrives at `/onboarding`
4. **Step 1 — YouTube:**
   - Enters YouTube Client ID and Client Secret (from Google Cloud Console)
   - Clicks “Authorize EN Channel” → Google consent → returns ✅
   - Clicks “Authorize FR Channel” → Google consent → returns ✅
5. **Step 2 — Google Translate:**
   - Pastes API key → clicks “Validate” → live test → ✅
6. **Step 3 — ElevenLabs:**
   - Pastes API key → clicks “Validate” → live test → ✅
7. **Step 4 — Hardware:**
   - Selects Epiphan or OBS
   - Enters IP / connection details → clicks “Test Connection” → ✅
8. **Step 5 — Ready:**
   - All green — “Miktos is ready. Start your first session →”
9. Returns to cockpit — banner is gone

Total time for a new operator: ~5 minutes, no terminal.

---

## Tests (`tests/test_phase_12_onboarding.py`)

~10 tests, FastAPI TestClient, mocked external calls:

1. `test_status_all_missing` — fresh `.env`, status returns all false
2. `test_status_partial` — some keys set, others missing
3. `test_write_env_key_new` — appends new key to `.env`
4. `test_write_env_key_update` — updates existing key, preserves others
5. `test_write_env_key_atomic` — temp file pattern, no partial writes
6. `test_validate_elevenlabs_success` — mock 200 response → key written
7. `test_validate_elevenlabs_failure` — mock 401 response → error returned, nothing written
8. `test_validate_translate_success` — mock translate response → key written
9. `test_validate_pearl_success` — mock Pearl API response → connection confirmed
10. `test_onboarding_index_renders` — GET /onboarding returns 200

**Prior tests unmodified. Target: 130 + ~10 = ~140 passed, 1 skip.**

---

## What Does Not Change

- `.env` is still the credential store — same as today
- `load_dotenv()` calls throughout the codebase — unchanged
- `youtube_auth.py` script — kept as a fallback CLI option
- Engine, coordinator, workers, monitors — not touched
- Existing web routes (`/`, `/setup`, `/sessions`) — unchanged except banner
- Architecture invariant — additive only

---

## Seal Criteria

- All tests pass, 130 prior tests unmodified
- A fresh `.env` with no credentials triggers the banner on the cockpit
- Completing all 5 wizard steps writes all credentials to `.env`
- Banner disappears after completion
- YouTube OAuth flow completes in-browser for both EN and FR channels
- ElevenLabs and Google Translate keys are validated live before being written
- Pearl connection test confirms device is reachable
- `youtube_auth.py` CLI still works unchanged as a fallback

---

## Constraints and Non-Goals

- **No OS keychain in Phase 12** — `.env` file is sufficient for local use.
  Keychain integration belongs to Phase 13 (Electron) where the OS APIs
  are available through the Electron main process.
- **No multi-user credential management** — Phase 14 concern.
- **No credential rotation reminders** — tokens expire; the banner will
  reappear when they do. Proactive reminders are a future polish item.
- **Google Cloud project setup not guided** — the operator must still
  create a Google Cloud project and enable the YouTube and Translate APIs.
  Phase 12 guides what to do with the credentials, not how to create them.
  A help link to the Google Cloud Console is sufficient for now.

---

*Spec written 2026-04-30.*
*Branch: `phase-12/onboarding-wizard` from `main` at `cc5b58d`.*
