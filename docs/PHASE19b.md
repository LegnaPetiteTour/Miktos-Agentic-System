# Phase 19b — Production Mode Cockpit Redesign

**Status:** COMPLETE
**Completed:** 2026-05-08
**Started:** 2026-05-07
**Branch:** `feat/mission-status-bar-and-ui-fixes`
**Final commit:** `6e0dc7a`
**Tests:** 251 passed, 1 skipped
**Affects:** `web/templates/`, `web/static/style.css`, `web/server.py` (additive routes only)  
**Does NOT affect:** Any API endpoint, backend logic, Python domain code, or tests

---

## 1. Why this redesign exists

The cockpit reached Phase 18 as a functional but device-centric layout:
all panels for all hardware were shown simultaneously, regardless of what
was actually connected or what production mode the operator was running.

Concrete problems observed in real operator use:

- **Pearl Inputs, raw health ticks, and the action log dominated the live
  view** — diagnostic data that belongs in a separate screen, not next to
  the Start button during a live event.
- **No concept of production mode** — OBS-only events still showed Pearl
  channel controls; Pearl-only events still showed OBS scene controls.
- **No pre-flight ritual** — operators landed directly inside the full
  cockpit with no guided checklist or mode selection.
- **Onboarding as a permanent top-level tab** — onboarding should happen
  once and then disappear into Setup, not persist as a nav item forever.
- **"EN Channel" / "FR Channel" column labels were misleading** — the
  left column held device controls (Pearl layouts, channel assignment,
  scene switcher, audio) that are not conceptually "EN channel" work.

This phase redesigns the UI around **production modes and operator intent**,
not around the physical device tree.

---

## 2. Research basis

The design borrows mental models from established professional tools:

| Tool | Mental model borrowed |
| --- | --- |
| **OBS** | Scene/source/audio as core production units |
| **Epiphan Pearl** | Confidence monitoring + channel state + layout carousel |
| **vMix** | Preview → Program workflow; inputs below |
| **Bitfocus Companion** | Simplified control surface; abstracted actions |
| **CasparCG / SPX** | Rundown/playlist as primary operator mental model |
| **YouTube Live Control Room** | Platform health/metadata separated from encoder |

The synthesis: Miktos should not copy any one tool. It should present an
**institutional operator cockpit** — safe, mission-focused, bilingual-aware —
that hides device complexity behind production-mode intent.

---

## 3. Design principles

1. **Mode decides visibility** — OBS-only mode hides all Pearl controls.
   Pearl-only mode hides OBS scene controls. No exceptions.
2. **Capabilities decide controls** — what is shown comes from the adapter
   contract (`AdapterCapabilities`), not hardcoded hardware names.
3. **State decides enabled/disabled/warning/hidden** — a control that cannot
   do anything right now is dimmed or hidden, not left active and broken.
4. **Diagnostic data stays out of the live cockpit** — Pearl Inputs, raw
   tick counts, full action log, and adapter health live in Diagnostics.
5. **Home first** — operators are guided through a pre-flight ritual before
   entering the live cockpit. The cockpit is not the default landing page.

---

## 4. Navigation structure

### Before (Phase 18)

```text
Cockpit | Setup | Sessions | Onboarding
```

### After (Phase 19b)

```text
Home | Produce | Setup | Sessions | Diagnostics
```

| Tab | Purpose | Notes |
| --- | --- | --- |
| **Home** | Pre-flight, mode selection, readiness | Default landing page |
| **Produce** | Live cockpit, mode-adaptive | Only meaningful after Home |
| **Setup** | Credentials, devices, templates, onboarding | Absorbs Onboarding |
| **Sessions** | Archive, history, reports | Unchanged |
| **Diagnostics** | Raw device data, health, logs | New; absorbs diagnostic panels |

Onboarding is **not removed** — it moves under Setup. The `/onboarding`
routes and all existing onboarding templates are preserved.

---

## 5. Home / Pre-flight page (`/home` or `/`)

The operator selects context before entering production. Device readiness
is read from the existing SSE stream — no new backend calls.

```text
┌──────────────────────────────────────────────┐
│  Miktos — Pre-flight                         │
├──────────────────────────────────────────────┤
│  Production Mode                             │
│  [Pearl Only] [OBS Only] [Pearl + OBS]       │
│  [Rehearsal]                                 │
├──────────────────────────────────────────────┤
│  Session                                     │
│  [Create New] [Load Existing] [Template]     │
├──────────────────────────────────────────────┤
│  Platform Destination                        │
│  [YouTube EN] [YouTube FR] [Both] [None]     │
├──────────────────────────────────────────────┤
│  Device Readiness                            │
│  OBS: ● Online   Pearl: ● Online             │
│  Captions: ○ Idle   Storage: ● OK            │
├──────────────────────────────────────────────┤
│            [Enter Production →]              │
└──────────────────────────────────────────────┘
```

Selected mode and destination are stored in `localStorage` so the Produce
cockpit can read them without any server round-trip.

---

## 6. Production mode logic

### Mode: Pearl Only

**Show:** Pearl Channels, Pearl Layouts, Pearl Preview, Pearl Stream/Record,
Captions, Run-of-Show, Pipeline  
**Hide:** OBS Scenes, OBS Source controls, OBS Audio mixer

### Mode: OBS Only

**Show:** OBS Preview/Program, OBS Scenes, OBS Audio, Graphics, Captions,
Run-of-Show, Pipeline  
**Hide:** Pearl Channels, Pearl Inputs, Pearl Layouts, Pearl Stream controls

### Mode: Pearl + OBS

**Show:** Both, grouped by topology. Active channel mapping is primary.

**Topology sub-choice** (stored in `localStorage`):

- Pearl primary / OBS secondary compositor
- OBS primary / Pearl as encoder/backup

### Mode: Rehearsal

**Show:** Full cockpit, all panels visible, prominent REHEARSAL banner.

**Behavioral:** Rehearsal flag already exists in backend (`data/state/rehearsal.json`);
UI simply reflects it.

---

## 7. Produce cockpit layout — three zones

```text
┌─────────────────────────────────────────────────────────────┐
│  Mission Status Bar (persistent, always visible)            │
│  Session | Mode | EN/FR | OBS | Pearl | Captions | Elapsed  │
├───────────────┬─────────────────────────────┬───────────────┤
│  LEFT RAIL    │  CENTRE STAGE               │  RIGHT RAIL   │
│               │                             │               │
│  Active       │  Preview / Program          │  Health       │
│  Channels     │  Current Cue                │  Captions     │
│  Sources      │  Next Cue                   │  Pipeline     │
│  Layouts      │  Run-of-Show                │  Emergency    │
│               │  Graphics / Lower Thirds    │  Action Log   │
│               │  Transitions                │  (compact)    │
└───────────────┴─────────────────────────────┴───────────────┘
```

**Left rail** — `cockpit-col-left`: mode-driven channel/source list.  
**Centre stage** — `cockpit-col-centre`: production controls, cue, preview.  
**Right rail** — `cockpit-col-right`: health monitor, captions, pipeline, emergency.

This replaces the current 4-column layout (EN Channel | Production | FR Channel | Health).

---

## 8. Default view: Institutional Operator

The default Produce view for Miktos is the **Institutional Operator** layout.
It is designed for government, municipalities, and bilingual events — not for
technically advanced broadcast engineers.

Priorities (top to bottom):

1. Session name + mode + live/rehearsal state
2. Current and next cue (run-of-show)
3. Active channel confidence (EN/FR status)
4. Preview thumbnails
5. Captions health
6. Emergency stop (always reachable)

Advanced controls (scene switcher, audio faders, graphics) are present but
visually subordinate — collapsed or in the right rail.

---

## 9. Diagnostics page (`/diagnostics`)

Panels moved out of the live cockpit and into Diagnostics:

| Panel | Current location | New location |
| --- | --- | --- |
| Pearl Inputs | Left rail | Diagnostics |
| Raw tick counter | Sidebar | Diagnostics |
| Full action log | Sidebar | Diagnostics (compact log stays in right rail) |
| Adapter health details | Health panel | Diagnostics |
| Hardware badge (raw) | Left rail | Diagnostics |

The right rail in Produce retains a **compact health summary** (3-line
colour-coded chip row: OBS / Pearl / Captions) — enough for a glance,
not the full diagnostic dump.

---

## 10. What is NOT changing

- No API endpoints are added, removed, or modified
- No Python domain code is touched
- No SSE stream payload changes
- No test files are changed
- All existing HTMX panel templates are preserved (may be reorganised but not rewritten)
- The adapter contract (`engine/adapters/`) is untouched
- Auth, Docker, and health-check behavior are untouched
- All 251 existing tests must remain green throughout

---

## 11. Execution plan

Each subphase is a separate commit. Each must leave tests green.

### Subphase 19b-1 — Navigation + Routing

Files: `web/templates/base.html`, `web/server.py`

- Rename "Cockpit" → "Produce", "Onboarding" removed from nav
- Add nav links: Home, Produce, Setup, Sessions, Diagnostics
- Add server routes: `GET /home`, `GET /produce`, `GET /diagnostics`
  (each returns a new template; existing `GET /` preserved as redirect)
- **Backend touch:** 3 additive routes in `server.py` only

### Subphase 19b-2 — Home / Preflight page

Files: `web/templates/home.html`, `web/static/style.css`

- Mode selector (4 buttons, `localStorage`)
- Destination selector
- Device readiness (reads existing SSE data)
- Enter Production button (navigates to `/produce`)
- No new API calls

### Subphase 19b-3 — Mode-aware Produce page

Files: `web/templates/produce.html` (or refactored `index.html`), `web/static/style.css`

- Three-zone layout (left rail / centre stage / right rail)
- JS reads `localStorage` mode on load, applies CSS class to root element
- CSS rules: `.mode-obs-only .pearl-zone { display:none }` etc.
- Mission Status Bar preserved; all SSE wiring preserved

### Subphase 19b-4 — Diagnostics page

Files: `web/templates/diagnostics.html`, panel template moves

- Move Pearl Inputs panel, raw ticks, full action log, hardware badge
- Right rail in Produce gets compact health chip replacing removed panels

---

## 12. Rollback plan

Since all changes are template/CSS only (except 3 additive server routes),
rollback is a single `git revert` of the relevant commit. The existing
`feat/mission-status-bar-and-ui-fixes` work is sealed at commit `0ffec3d`
and is the safe restore point before this phase began.

---

## 13. Completion gate

- [x] All 251+ tests green (no regressions)
- [x] Navigation shows: Home | Produce | Setup | Sessions | Diagnostics
- [x] Selecting “OBS Only” on Home hides Pearl panels in Produce
- [x] Selecting “Pearl Only” on Home hides OBS panels in Produce
- [x] Pearl Inputs and raw ticks are NOT visible in Produce (Diagnostics only)
- [x] Emergency Stop remains reachable in all modes
- [x] Mission Status Bar is visible in all Produce views
- [x] No backend API changes

---

*Document created: 2026-05-07*
*Completed: 2026-05-08*
*Author: Miktos Engineering*
*Continued in: `docs/PHASE19c.md`*
