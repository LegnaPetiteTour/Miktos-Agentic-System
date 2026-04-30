# Miktos — Product Vision

**Created:** 2026-04-30
**Status:** Planning — prototype complete, product path defined

---

## What Miktos Is

Miktos is a bilingual live-stream production system for institutional media
teams. It automates everything that happens after a stream ends: downloading
recordings from hardware, extracting audio, transcribing both languages,
updating YouTube channels, and producing a session archive with proof of
what was streamed.

A single operator, with one click in a browser, can run a complete
bilingual EN/FR live stream and receive a fully processed session folder
within minutes of the stream ending.

---

## The Problem It Solves

Bilingual institutional live streaming currently requires:
- Manual recording management across multiple hardware devices
- Manual audio extraction and transcription
- Manual YouTube metadata updates for two channels
- No automatic archive of what was streamed
- No transcript for media accountability

Miktos eliminates all of this. One session produces:
- EN + FR recordings (proof of what was streamed per channel)
- EN + FR audio (MP3)
- EN + FR transcripts (media accountability record)
- YouTube EN + FR metadata updated automatically
- Session report with per-slot status

---

## Target User

**Primary:** Communications operators at bilingual institutions —
government agencies, NGOs, universities, media organizations —
who manage live streams and need post-stream processing to be
automatic and auditable.

**Secondary:** Single-operator content creators who stream to
multiple YouTube channels and want automated post-stream workflows.

**Not (yet):** Large broadcast organizations with dedicated engineering
teams and custom infrastructure.

---

## What "Done" Looks Like

A communications operator at a bilingual institution can:

1. Download and install Miktos from a `.dmg` or package manager
2. Open the app, complete a guided setup wizard (YouTube, ElevenLabs, hardware)
3. Before a stream: open the Miktos app, confirm session name, click Start
4. After the stream: stop the hardware recording, click Stop in Miktos
5. Receive a complete session archive within 2 minutes of stopping
6. Never touch a terminal, never edit a config file

That is the product. Everything before it is prototype.

---

## Current State (2026-04-30)

Phases 0–11 delivered a working prototype validated in production:
- Bilingual EN/FR pipeline works end-to-end
- 130 tests passing, 1 permanent skip
- Web cockpit operational (browser-based, local)
- Session folder with 7 files produced automatically

**What still requires a developer:**
- Installation (Python venv, pip, git clone)
- Credential setup (manually editing `.env` files)
- Understanding which terminal commands to run
- Knowledge of Pearl/OBS configuration

---

## Product Path

Three stages. Each unlocks the next. No stage is skipped.

### Stage 1 ✅ COMPLETE — Local prototype

Working system on one developer's Mac. Validated in production.
Phases 0–11.

### Stage 2 🕑 IN PROGRESS — Local installable app

The same system, packaged so a non-technical operator can install
and configure it without developer assistance.

**Key milestones:**
- Phase 12: First-run onboarding wizard (credentials, hardware setup)
- Phase 13: Electron packaging (.dmg Mac app)

**Why Electron first:**
- Preserves the existing Python backend unchanged
- The web cockpit already exists as the UI — Electron wraps it
- No new architecture, no new language, no cloud infrastructure
- Local-first means all problems are solved before adding remote complexity
- Every institution can test it locally before any IT involvement

### Stage 3 🕑 FUTURE — Self-hosted web app

Docker container deployable on an institution's own infrastructure.
Multi-operator access, auth, local network access.

**Depends on:** Stage 2 validated at multiple institutions.

### Stage 4 🕑 FUTURE — Hosted SaaS

Cloud-hosted, multi-tenant, subscription model.

**Depends on:** Stage 3 validated. Requires solving data sovereignty.

---

## What Stage 2 Requires (in order)

### 1. Operator onboarding (Phase 12) — highest priority

The single biggest gap between prototype and product.

Phase 12 adds a first-run wizard to the web cockpit:
- Detects missing credentials on startup
- Walks through YouTube OAuth in-browser (no terminal)
- Accepts ElevenLabs API key with immediate validation
- Guides Pearl IP / OBS selection with connection test
- Stores credentials securely (OS keychain or encrypted local file)
- Shows a clear "Ready" state when setup is complete

### 2. Electron packaging (Phase 13)

After onboarding works cleanly:
- Bundle Python runtime + FastAPI server inside an Electron app
- Standard `.dmg` installer for macOS
- App auto-starts the web server, opens the cockpit in a window
- Menu bar icon shows session state
- No terminal needed after initial install

---

## Constraints

**Budget:** Limited. No cloud infrastructure spend until Stage 3 has
a paying customer. All Stage 2 work is local, zero ongoing cost.

**Hardware dependency:** Full bilingual workflow requires Epiphan Pearl.
OBS path works on any machine. Stage 2 must work without Pearl
(OBS-only mode) to broaden the addressable audience.

**Team:** Solo developer (Angel Torrella). Consistent progress,
no rush. Each phase production-validated before the next begins.

---

## Success Metric for Stage 2

A communications officer at a bilingual institution who has never used
Miktos can install it, complete setup, and run their first bilingual
session without any help from the developer.

That is the bar. Nothing less.

---

*Written 2026-04-30. Prototype (Phases 0–11) complete.*
*Stage 2 begins with Phase 12 — operator onboarding wizard.*
