# Phase 19c — Layout Foundation Pass (Cockpit Perfection)

**Status:** PLANNED
**Branch:** `feat/phase-19c-layout-perfection`
**Depends on:** Phase 19b (complete — commit `6e0dc7a`)
**Affects:** `web/templates/`, `web/static/style.css` (CSS only, no Python changes)
**Does NOT affect:** Any API endpoint, backend logic, Python domain code

---

## 1. Why Phase 19c exists

Phase 19b established the correct architecture:

- Mode-first navigation (Home → Produce)
- Three-zone Produce layout (Left / Centre / Right)
- Diagnostics as a separate page
- SSE-driven compact health chip

Phase 19c is a **layout foundation pass** — not a feature pass. The architecture
is correct. What is wrong is the visual weight and operator experience:

| Page | Current problem |
| --- | --- |
| **Home** | Small centered card floating in empty dark space — looks like a developer settings panel, not a mission pre-flight |
| **Produce** | Preview thumbnails buried in right rail; Session + Stream as separate full-width panels consuming center space; no mode-specific feel |
| **Mission bar** | Terse tokens (`SESSION`, `EN`, `OBS`) instead of readable operator labels |
| **Diagnostics** | Unstructured 2-column with no clear section hierarchy |
| **Setup** | Flat unsectioned form — one long vertical dump of fields |
| **Sessions** | Narrow table floating in empty space; no detail affordance |
| **Typography** | Monospace used everywhere — logs feel identical to controls |

---

## 2. Design principles (unchanged from 19b, applied more strictly)

1. **Mode decides visibility** — same as 19b. Reinforced in 19c by making each mode feel like a distinct environment in the center stage.
2. **Operator confidence > diagnostic data** — preview thumbnails are primary visual content, not secondary.
3. **Center stage = current mission** — the center column is dominated by what the operator needs to act on now: Current Cue + Preview + Primary Controls.
4. **Typography distinguishes purpose** — sans-serif for operator-facing UI; monospace reserved for logs, IDs, timestamps, diagnostic data.
5. **No backend changes** — every change is template or CSS.

---

## 3. Gap analysis — current state vs. target

### 3.1 Home

**Current:** One centered `.home-card` with a narrow max-width. Looks like a modal.

**Target:** A real full-width dashboard with three columns:

```text
┌──────────────────────────────────────────────────────────────┐
│ Pre-flight                                                   │
│ Select session, verify production mode, check readiness.     │
├───────────────────────┬───────────────────────┬──────────────┤
│ Session               │ Production Mode        │ Readiness    │
│ Current: archive      │ ● Pearl Only           │ ● OBS OK     │
│ Template: Press Conf  │ ○ OBS Only             │ ● Pearl OK   │
│ YouTube EN/FR         │ ○ Pearl + OBS          │ ○ Captions — │
│                       │ ○ Rehearsal            │ ● Storage OK │
├───────────────────────┴───────────────────────┴──────────────┤
│ Warnings                                                     │
│                                  [Enter Production →]        │
└──────────────────────────────────────────────────────────────┘
```

**Changes required:**

- Replace `.home-wrap > .home-card` single-column with `.home-dashboard` 3-column grid
- Left column: Session block (current session from SSE, template placeholder, destination labels)
- Centre column: Production mode buttons (existing 4 buttons, restyled)
- Right column: Device readiness (existing SSE dots, restyled)
- Footer row: Warnings area + Enter Production button (full width)
- CSS: `.home-dashboard`, `.home-col`, `.home-col-label`, `.home-footer-bar`

### 3.2 Produce — Mode-specific center stage

**Current:** Center stage stacks: Session panel → Stream panel → Run-of-Show → Pipeline → Graphics.
Preview is in the right rail. Mode affects left rail visibility only.

**Target:** Center stage is dominated by the active preview strip and current cue.
Session + Stream collapse to a compact control strip directly above the cockpit grid.
Each mode feels like a different environment because the center content changes.

```text
After mission bar:
┌──────────────────────────────────────────────────────────────┐
│ [Stop Session]  Stream: LIVE  Elapsed: 00:32:14  [Rehearsal] │  ← compact control strip
└──────────────────────────────────────────────────────────────┘
┌───────────────────┬───────────────────────────────┬──────────┐
│ LEFT RAIL         │ CENTRE STAGE                   │ RIGHT    │
│                   │                                │          │
│ Pearl Only:       │ Preview Strip (3 thumbnails)  │ Health   │
│  Layouts          │  [EN] [FR] [OBS]              │ Captions │
│  Channels         │                                │ Pipeline │
│                   │ Current Cue / Run-of-Show      │ Emergency│
│ OBS Only:         │                                │ Rehearsal│
│  Scenes           │ Primary Controls               │          │
│  Audio            │  (graphics, transitions,       │          │
│                   │   lower thirds)                │          │
│ Pearl+OBS:        │                                │          │
│  Both             │                                │          │
└───────────────────┴───────────────────────────────┴──────────┘
```

**Changes required:**

- Move `panel_preview` from right rail → centre stage (top of centre column)
- Replace `panel-control` (Session) + `panel-stream` (Stream) with a single
  compact `.cockpit-control-strip` directly above the cockpit grid
- Keep Run-of-Show, Pipeline, Graphics in centre (Pipeline moves to right rail)
- Right rail: remove preview HTMX div; add compact pipeline; keep health chip,
  captions, safe_mode, rehearsal
- Pearl Inputs already in Diagnostics (done in 19b-4) — add a
  `pearl-inputs-summary` chip in the left rail for `pearl-only` / `pearl-obs` modes
  showing "N inputs discovered → Diagnostics"

### 3.3 Mission bar — readable pills

**Current:** `SESSION archive | LIVE | EN | FR | OBS | PEARL | CAPTIONS | ELAPSED`
Terse, cryptic, developer-telemetry feel.

**Target:**

```text
Session: archive  |  Mode: Pearl + OBS  |  State: LIVE  |  Stream: STOPPED
OBS: Offline  Pearl: Online  Captions: Stale  |  Elapsed: 01:45:22
```

Full readable labels and values as pill pairs. LIVE badge color-coded green;
REHEARSAL amber; STOPPED/OFFLINE red.

**Changes required:**

- In `index.html`, change `msb-label` text from `SESSION` → `Session:`,
  `EN` → `EN Channel:`, `OBS` → `OBS:`, etc.
- Add `Mode:` chip reading from `localStorage` (not SSE — set at page load from mode)
- `Stream:` chip reading from SSE `stream_state`
- Minor CSS tweaks to make labels and values display as inline readable text

### 3.4 Diagnostics — structured 3-column layout

**Current:** 2-column grid (`.diag-col` each side), info strip at top.
Left column feels unstructured; Pearl Inputs are shown but section hierarchy is weak.

**Target:**

```text
┌──────────────────────────────────────────────────────────────┐
│ Diagnostics                                                  │
│ Hardware: X | Session: Y | Ticks: N | Alerts: — | Elapsed:  │
├───────────────────────┬───────────────────────┬──────────────┤
│ Device Health         │ Adapter Logs           │ Raw Inputs   │
│ OBS: Offline          │ Action log (full)      │ Pearl Inputs │
│ Pearl: Online         │                        │ EN / FR feeds│
│ Captions: Stale       │                        │ OBS Sources  │
│ Network: OK           │                        │              │
├───────────────────────┴───────────────────────┴──────────────┤
│ Pipeline Slots                                               │
└──────────────────────────────────────────────────────────────┘
```

**Changes required:**

- Replace 2-column `.diag-grid` with 3-column layout
- Column 1: Device Health (HTMX `/panels/health`)
- Column 2: Adapter Logs = Action log (HTMX `/panels/action_log`)
- Column 3: Raw Inputs = Pearl feed EN + FR (HTMX)
- Full-width footer: Pipeline Slots (SSE-driven)

### 3.5 Setup — grouped cards

**Current:** Flat form with all fields in one vertical list.

**Target:**

```text
┌──────────────────┐ ┌──────────────────┐
│ Session Identity │ │ Hardware         │
│ Event Name       │ │ Production mode  │
│ Template (future)│ │ Pearl host       │
└──────────────────┘ │ OBS WebSocket    │
                     └──────────────────┘
┌──────────────────┐ ┌──────────────────┐
│ Channels         │ │ Destinations     │
│ EN source        │ │ YouTube EN ID    │
│ FR source        │ │ YouTube FR ID    │
└──────────────────┘ └──────────────────┘

[Save Config]  [Validate Setup ✗ — not connected]
```

**Changes required:**

- Wrap existing form fields into `.setup-group` card containers with group headers
- Add disabled `Validate Setup` button (no endpoint exists; marked disabled with tooltip)
- No new API calls; validation endpoint deferred

### 3.6 Sessions — wider table

**Current:** Single narrow panel, table with 3 columns.

**Target:** Full-width panel, wider table, date column added, prepared for future
2-column split (session list + detail pane). No detail pane built yet — just
structure added.

**Changes required:**

- Wrap sessions panel in `.sessions-layout` flex container (prepared for future left/right split)
- Add `Date` column to table (parsed from session name if ISO-like)
- Widen layout; remove fixed narrow max-width

### 3.7 Typography — sans-serif for UI

**Current:** `font-family: monospace` or similar applies to most text.

**Target:**

- CSS variable `--font-ui: 'Inter', system-ui, -apple-system, sans-serif`
- CSS variable `--font-mono: 'JetBrains Mono', 'Fira Code', 'Menlo', monospace`
- Apply `--font-ui` to: panel headers, button labels, form labels, nav links,
  mode buttons, home dashboard, mission bar
- Keep `--font-mono` for: action log entries, ID values, timestamps, diagnostics
  raw data, captions text
- Slightly increase base font size from ~0.82rem to ~0.88rem for operator text

---

## 4. What is NOT changing

- No API endpoints added, removed, or modified
- No Python domain code touched
- No SSE stream payload changes
- Existing HTMX panel templates preserved (reorganised, not rewritten)
- Auth, Docker, health-check untouched
- All 251+ tests must remain green throughout

---

## 5. Execution plan

Each subphase is a separate commit. Each must leave tests green.

### Subphase 19c-1 — Home dashboard

**Files:** `web/templates/home.html`, `web/static/style.css`

- Replace `.home-card` single-column with `.home-dashboard` 3-column grid
- Session column (left): current session name from SSE, destination labels
- Mode column (centre): existing 4 mode buttons, restyled
- Readiness column (right): existing SSE-driven dots, restyled
- Footer bar: warnings area + Enter Production button
- CSS: remove `.home-card` styles; add `.home-dashboard`, `.home-col`, `.home-footer-bar`

### Subphase 19c-2 — Produce center stage + control strip

**Files:** `web/templates/index.html`, `web/static/style.css`

- Add `.cockpit-control-strip` above cockpit grid (replaces `panel-control` + `panel-stream`)
  - Left: Start/Stop session buttons
  - Centre: Stream state badge + elapsed
  - Right: Rehearsal indicator
- Move `panel_preview` HTMX div from right rail → top of centre column
- Add `pearl-inputs-summary` section in left rail (pearl-zone) showing discovered
  inputs count + link to Diagnostics (no API call — static text with SSE count if available)
- Move Pipeline panel from centre → right rail (compact)
- Right rail: remove `panel_preview` HTMX load; add compact pipeline section
- Update tests affected by `panel-stream` removal → new `cockpit-control-strip` check

### Subphase 19c-3 — Mission bar + typography pass

**Files:** `web/templates/index.html`, `web/static/style.css`

- Mission bar: replace terse tokens with readable `Label: value` pills
  - Add `Mode:` chip from localStorage on DOMContentLoaded
  - Add `Stream:` chip from SSE `stream_state`
  - Change `SESSION` → `Session:`, `EN` → `EN:`, `FR` → `FR:`, etc.
- CSS: add `--font-ui` and `--font-mono` variables
- Apply `font-family: var(--font-ui)` to panel titles, buttons, labels, nav, home
- Keep `font-family: var(--font-mono)` for logs, IDs, timestamps
- Increase operator text from ~0.82rem → 0.88rem in key places

### Subphase 19c-4 — Diagnostics 3-col + Setup groups + Sessions widen

**Files:** `web/templates/diagnostics.html`, `web/templates/setup.html`,
`web/templates/sessions.html`, `web/static/style.css`

- Diagnostics: replace 2-col with 3-col (Health | Logs | Raw Inputs); full-width pipeline strip
- Setup: wrap fields in `.setup-group` cards with section headers; add disabled Validate button
- Sessions: widen table; add Date column; wrap in `.sessions-layout` for future 2-col

---

## 6. Test impact

| Test file | Affected check | Action |
| --- | --- | --- |
| `test_phase_10a_web.py` | `panel-stream` in produce | Update to check `cockpit-control-strip` |
| `test_phase_18.py` | Column class checks | Verify after control strip change |
| All others | No change expected | Verify green after each subphase |

---

## 7. Completion gate

- [ ] All 251+ tests green (no regressions)
- [ ] Home is a 3-column dashboard, not a floating card
- [ ] Preview thumbnails are in the centre stage of Produce, not the right rail
- [ ] Session + Stream are a compact control strip, not two full panels
- [ ] Mission bar uses `Label: value` format, readable under stress
- [ ] `Pearl Only` mode shows only Pearl controls in left rail + EN/FR preview
- [ ] `OBS Only` mode shows only OBS controls in left rail + OBS preview
- [ ] `Pearl + OBS` mode shows both with full preview strip
- [ ] `Rehearsal` mode shows everything with prominent banner
- [ ] Diagnostics has 3 clear columns: Health | Logs | Raw Inputs
- [ ] Setup fields grouped into 4 labeled cards
- [ ] Sessions table is full-width
- [ ] Operator-facing text uses sans-serif; logs/IDs use monospace
- [ ] No backend API changes

---

*Document created: 2026-05-08*
*Author: Miktos Engineering*
*Builds on Phase 19b (complete, commit `6e0dc7a`)*
