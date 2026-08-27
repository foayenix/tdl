# BUILD.md — The Deposit Ledger

**Read this file and `DESIGN.md` at the start of every session before writing any code.** They are the contract. If something you are about to do contradicts either, stop and say so instead of doing it.

- `DESIGN.md` — the visual contract: tokens, type, spacing, component states, per-screen specs.
- `docs/spec.md` — the original rationale: why SQLite, the enrichment sources, the scope argument.
- `design/artboards.dc.html` — ten artboards, four doubled in dark. **The artboards are the final authority.**

---

## 0 · Session protocol

Work is done in **30-minute sessions**. Each session:

1. Read `BUILD.md`, `DESIGN.md`, `STATE.md`.
2. Take the next unchecked item in §6. Do not skip ahead. Do not do two.
3. Build until it **runs**. Not until it is elegant.
4. Run `just check` (§7). It must pass.
5. Update `STATE.md`: what landed, what broke, where the next session starts.
6. Commit — one per session, message `session NN — <what now works>`.

Overrun means **stop anyway** and carry the remainder. Never leave the repo where `just check` fails; if you cannot fix it inside the session, revert to the last green commit and write the problem into `STATE.md`.

---

## 1 · Scope reckoning — read this before planning anything

The design grew from four artboards to ten, and four of those are now doubled in dark. That is roughly **three times** the original surface. The original plan was 20 × 30-minute sessions finishing before 5 October. It no longer fits, and pretending otherwise is how the tool starts eating the monograph block — the exact failure `docs/spec.md` §09 warns about.

So the release is split. **v0.1 is frozen at five screens, light theme only.**

| | screens | why |
|---|---|---|
| **v0.1** — by 5 Oct | 01 system · 02 today · 03 corpus · **05 monograph** · 04 wall | The daily loop, end to end: log a day, find a plant, write the record, see what you have published. |
| **v0.2** — after a month of daily use | 06 library · 09 capture overlays · dark theme · state 3 | Everything here is a speed-up of work that v0.1 already makes possible. |
| **v0.3** | 07 overview | Analytics over fourteen months of data you do not have yet. Building it now means designing against invented numbers. |

**Artboard 05 (monograph) is in v0.1 and does not move.** A corpus table with no detail view is a list of names — the record *is* the product. If v0.1 slips, **The Wall is cut first**, then corpus filters, then the fourteen-day table. Not the monograph screen.

Say plainly in `STATE.md` when a session reveals this plan is wrong. Do not quietly extend it.

---

## 2 · What this is

A single-user, offline-first desktop application for logging daily research work and building a medicinal-plant materia medica corpus. One SQLite file on one Mac. No server, no account, no sync, no other user — ever.

Records form one graph: a **daily entry** points at the **monograph** written that day, which carries sourced **claims** (vernaculars, indications, constituents, safety findings) citing **references**, which feed the **outputs** published. The connectedness is the whole value. The system must answer, in one query: *which plants have I written about that have no human-trial evidence and that I have never published on?*

### Non-goals — do not build, do not suggest

Authentication, accounts, multi-user anything · cloud sync or a hosted backend · a mobile app (phone capture is a text file, §5) · an ORM · a plugin system or theming engine · telemetry of any kind · an LLM writing into the corpus.

### The hard rule

The tool must never become more interesting than the work it records. If a session runs long, the tool loses. A perfect tracker with forty records is a failed project; a scruffy one with twelve hundred is the thing a reputation is built on.

---

## 3 · Architecture

```
┌──────────────────────────────────────────────┐
│  Tauri v2 desktop app                        │
│  ├── src/          TypeScript + Vite         │
│  └── src-tauri/    Rust core                 │
│         rusqlite ──────────┐                 │
└────────────────────────────┼─────────────────┘
                             │
                   ~/Documents/ledger.sqlite   ← single source of truth
                             │      (WAL mode)
┌────────────────────────────┼─────────────────┐
│  `ledger` — Python CLI  ───┘                 │
│  log · seed · inbox · enrichment · import    │
│  · Anki export · migrations                  │
└──────────────────────────────────────────────┘
```

The CLI is named **`ledger`**, per artboard 08 (`ledger seed --from ~/notes/plants.csv`). Earlier drafts called it `dep`; that name is retired.

### Ownership rule — memorise this

| Concern | Owner | |
|---|---|---|
| Schema + migrations | **Python** (`ledger migrate`) | Rust reads `PRAGMA user_version`, refuses to start if it does not match what it was compiled against, and never migrates. |
| Network enrichment — Crossref, GBIF, WFO | **Python** | Rust has no HTTP client. The app calls the CLI as a sidecar. |
| UI reads and simple writes | **Rust** (rusqlite) | Plain SQL; the CLI does these directly too. |
| Bulk import, Anki export, seeding | **Python** | Never in the app. |

Enrichment — name resolution, confidence thresholds, DOI normalisation — is where bugs are expensive and silent. It exists in exactly one language.

Both processes may hold the database open at once: `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` on every connection, both sides, tested explicitly (§7).

### Stack, pinned

- **Tauri v2** — Rust core, system webview, no Electron.
- **Frontend:** TypeScript + Vite. Vanilla DOM or Preact — pick in session 12, record it. **No React, no Tailwind, no component library, no CSS framework.** `DESIGN.md` is small enough to be hand-written CSS and that is the intended amount.
- **Rust:** `rusqlite` with `bundled` (compiles SQLite in; FTS5 available), `serde`, `tauri-plugin-shell`.
- **Python:** 3.12+, **stdlib only** for the CLI (`argparse`, `sqlite3`, `urllib.request`, `json`). Permitted exceptions: `pyinstaller` (build-time, freezes the sidecar) and `datasette` + `sqlite-utils` (developer tools, never shipped).
- **Charts (v0.3):** hand-written inline SVG. No charting library. All four charts in artboard 07 are polylines, squares and filled rects.

### The sidecar

The frozen `ledger` binary ships inside the app so enrichment works on a machine with no Python.

```json
// src-tauri/tauri.conf.json
{ "bundle": { "externalBin": ["binaries/ledger"] } }
```

The file on disk carries the target triple — `binaries/ledger-aarch64-apple-darwin` on Apple Silicon. Find it with `rustc --print host-tuple`.

```json
// src-tauri/capabilities/default.json
{ "identifier": "shell:allow-execute",
  "allow": [{ "name": "binaries/ledger", "sidecar": true }] }
```

Invoke from Rust, never the frontend — the frontend must not hold shell permissions:

```rust
use tauri_plugin_shell::ShellExt;
let cmd = app.shell().sidecar("ledger")?;
```

Every enrichment subcommand supports `--json`. Every sidecar call has a timeout and a visible inline failure state. Network calls fail; the app stays usable when they do.

---

## 4 · Data model — schema v4

Artboard 08 shows `schema v4`. Four migrations, applied in order, `user_version` stamped by each.

- `000_init.sql` — `entry`, `monograph`, `reference`, `output`
- `001_claims.sql` — `vernacular`, `indication`, `constituent`, `safety`, `benefit_sharing`
- `002_links.sql` — `monograph_reference` (with `section`), `output_monograph`, `reference_tag`, `inbox_line`
- `003_fts.sql` — FTS5 virtual table + sync triggers on insert, update **and** delete

### Fields the design requires

Read the artboards for the full set; these are the ones easy to miss.

**monograph** — `accepted_name`, `authority`, `family`, `part`, `habitat_note`, **`wfo_id`**, **`gbif_key`**, `gbif_confidence`, `status`, `summary`, `summary_rewritten_at`, **`preparation`**, `first_written`, `last_touched`.

**reference** — `doi` *or* `isbn`, `title`, `authors`, `journal`, `volume`, `year`, `type`, `access`, **`read_state`** (`queued|reading|read`), `added_at`, `added_from`, **`opened_count`**, **`why_it_mattered`**, `why_edited_at`.

**benefit_sharing** — `narrative`, `agreement_ref`, `expires`, `consent_recorded_at`. One row per monograph.

**Every claim row** (`vernacular`, `indication`, `constituent`, `safety`) carries a `source` — a `reference_id`, or free text for a field record. NULL or empty means unsourced.

**indication** additionally carries `tradition` and `region` — a claim is *who used it for what, where*, not just a condition string.

### Three enums — do not rename these values

```
monograph.status     skeleton | drafted | sourced | reviewed
indication.evidence  traditional_only | in_vitro | in_vivo | human_uncontrolled | rct | meta_analysis
safety.severity      critical | caution | note
```

Evidence displays as `E1`–`E6`. A monograph's headline evidence is the **maximum** across its indications.

### Two invariants — enforce in the database, not only the UI

1. **Sourcing.** `monograph.status` cannot become `reviewed` while any claim row belonging to it has an empty source. A trigger, plus a test that proves the trigger fires.
2. **Naming.** Never let an unresolved name into `monograph.accepted_name`. Below the GBIF confidence threshold (default 0.90) the record stays `skeleton` and enters the review queue. Store the **WFO-ID** as well as the name — names change, IDs do not. One bad name propagates into every query and paper and is not noticed for two years.

### Queries that must work on day one

```sql
-- current streak
SELECT count(*) FROM entry
WHERE date >= (SELECT max(date) FROM entry
               WHERE date NOT IN (SELECT date(date,'+1 day') FROM entry));

-- studied but never published on  → corpus footer, permanently visible
SELECT m.accepted_name, m.status
FROM monograph m
LEFT JOIN output_monograph om ON om.monograph_id = m.id
WHERE om.output_id IS NULL AND m.status IN ('sourced','reviewed')
ORDER BY m.first_written;

-- cited by nothing  → library filter
SELECT r.id, r.title FROM reference r
LEFT JOIN monograph_reference mr ON mr.reference_id = r.id
WHERE mr.monograph_id IS NULL;
```

### The git habit

The `.db` is binary and is never committed. A text dump goes beside it and is the historical source of truth:

```bash
sqlite3 ledger.sqlite .dump > dump/ledger.sql
git add dump/ledger.sql schema/ && git commit -m "ledger $(date +%F)"
```

`just dump` does this. Any commit rebuilds with `sqlite3 new.db < dump/ledger.sql` — proven by a test (§7).

---

## 5 · Capture

Capture friction kills systems like this. If logging a paper takes more than ten seconds it stops within a fortnight. Three routes, in order of use.

**Keyboard, in-app** (artboard 09) — `/` opens find; quick-add parses a command line into chips; DOI paste resolves against Crossref; inbox review routes phone lines with number keys. The app is usable from the keyboard alone during a work block.

**CLI** — the terminal is already open:

```
ledger log --minutes 90 --note "Khaya bark, 3 refs"
ledger mono "Khaya senegalensis" --part "stem bark"
ledger ref 10.1016/j.jep.2019.112202
ledger win note "Evidence grading for traditional-use claims" --url https://…
ledger find "antimalarial bark"
ledger seed --from ~/notes/plants.csv
ledger inbox
```

**Phone inbox** — not an app. An Apple Shortcut appends one line to a text file in iCloud Drive:

```
2026-08-24T07:42 mono Warburgia ugandensis bark — check the Kenyan trade figures
2026-08-24T09:15 ref 10.1016/j.jep.2026.118442
2026-08-24T18:57 bissilon?
```

`ledger inbox` parses pending lines, routes them, marks them consumed, and leaves anything it cannot classify in place for the review overlay. Offline-safe, no API keys, two taps. The nav shows a badge when lines are unconsumed.

**Bulk import** — one throwaway script per source, run once, deleted. Do not build a general importer.

---

## 6 · Build plan — v0.1

Thirty sessions. Tick each box as it lands.

**Week 1 — foundation**

- [x] 01 · Repo, `justfile`, `.gitignore`, `STATE.md`, Python package skeleton
- [x] 02 · `000_init.sql` + `ledger migrate` with `user_version` + dump/restore round-trip test
- [x] 03 · `ledger log` — writes an entry, prints the streak
- [x] 04 · `ledger mono` — skeleton, `$EDITOR` template, status transitions
- [x] 05 · `ledger win` — output linked to today's entry

**Week 2 — the corpus in the database**

- [x] 06 · `001_claims.sql` + the sourcing trigger + its test
- [x] 07 · `002_links.sql` + `ledger link` + `ledger seed`
- [x] 08 · `ledger ref` + Crossref, `--json`, DOI normalisation, offline failure path
- [x] 09 · GBIF resolver, confidence threshold, review queue
- [x] 10 · `003_fts.sql` — FTS5 + triggers + `ledger find`
- [x] 11 · `just dump` + pre-commit hook; restore-from-any-commit test

**Week 3 — shell and components**

- [x] 12 · `cargo tauri init`, window, WAL connection, `user_version` guard; pick vanilla vs Preact
- [x] 13 · **Artboard 01** — every token as a CSS variable, fonts self-hosted
- [x] 14 · **Artboard 01** — component specimens with all five states (§4 of `DESIGN.md`)
- [x] 15 · Left nav, live counts, real footer (path, size, last write)
- [x] 16 · Table primitive — column widths, row heights, hover/selected, **the unsourced row**

**Week 4 — today and corpus**

- [x] 17 · **Artboard 02** — stat row, floor toggle
- [x] 18 · **Artboard 02** — autosaving note + the three deposit rows
- [x] 19 · **Artboard 02** — fourteen-day table; sidecar wired to `Fetch`
- [x] 20 · **Artboard 03** — corpus table
- [x] 21 · **Artboard 03** — filter rail, URL-hash state
- [x] 22 · **Artboard 03** — `find` + FTS, live hit count, footer counts

**Week 5 — the monograph record**

- [x] 23 · **Artboard 05** — header, identity strip, summary strip
- [x] 24 · **Artboard 05** — vernacular + indication sections, inline add
- [ ] 25 · **Artboard 05** — constituent + safety sections, severity chips
- [ ] 26 · **Artboard 05** — prose sections: summary, preparation, benefit-sharing
- [ ] 27 · **Artboard 05** — references section, sticky rail, the reviewed-status block

**Week 6 — states, wall, ship**

- [ ] 28 · **Artboard 08** states 1, 2, 4, 5, 6 (skip 3 — overload, v0.2)
- [ ] 29 · **Artboard 04** — the wall
- [ ] 30 · PyInstaller freeze, `cargo tauri build`, launch from `/Applications` on a machine with no Python, `README.md`, tag `v0.1`

**Backfill to 40 real records happens alongside, not after.** Seed session 03 with the three plants known best. Opening a tool that already contains real work is what makes it worth opening tomorrow.

**Anki export** (v0.2) is a TSV of front, back, tags — Anki imports that natively, no library. One deck per field type (name→vernacular, plant→indication, plant→contraindication) so a type can be suspended without losing the rest.

---

## 7 · Definition of done

`just check` runs, in order:

```
ruff check ledger/          (skip silently if unavailable)
python -m pytest ledger/tests -q
cargo fmt --check && cargo clippy -- -D warnings
cargo test
```

### Tests that must exist and must never be deleted

1. **Dump round-trip** — build, dump, restore into a fresh file, assert every table identical.
2. **Concurrent access** — Rust core and a `ledger` process write to the same database in one test, both under WAL, neither raises `database is locked`.
3. **Migration ladder** — `000`→`003` from empty; assert `user_version` at each step; assert FTS triggers fire on insert, update **and** delete.
4. **Sourcing invariant** — a monograph with one unsourced claim row cannot reach `reviewed`; sourcing the row then allows it.
5. **Name resolution** — below-threshold GBIF match leaves `status='skeleton'` and writes nothing to `accepted_name`.
6. **Crossref parsing** — against a recorded fixture, never the live network. One live test marked `@pytest.mark.network`, excluded from `just check`.
7. **Streak query** — no entries, one entry, gap yesterday, gap today, entries out of order.
8. **Gap queries** — a monograph with an output does not appear; one without does. A reference bound to nothing appears in `cited by nothing`.

### Manual check at the end of every UI session

Screenshot the screen, open the artboard beside it, list every difference in `STATE.md`. Fix what is wrong; record what is deliberate and why. On a dark-theme session (v0.2) do both themes — dark is authored separately and cannot be checked by inverting the light screenshot.

---

## 8 · Guardrails

- **Do not add a dependency** without one line in `STATE.md` saying what it replaced and why stdlib was not enough.
- **Do not derive a colour.** No opacity tricks, no `lighten()`, no computed dark theme. Every value is in `DESIGN.md` because it was chosen.
- **Do not refactor** working code that is not in the way of the current item.
- **Do not write an abstraction** with one caller. Three, then abstract.
- **Do not build a general case** for a specific need. The importer is per-source and disposable.
- **Do not make up botanical data.** No placeholder plants, no invented DOIs, no lorem ipsum anywhere near the corpus. Empty states say what artboard 08 says they say. The species in the artboards are real and are design fixtures for artboard 01 only — never seed data.
- **Do not let a model write into the corpus.** Provenance is why the corpus is worth anything.
- **Do not soften artboard 07.** Its charts exist to show that private notes are not public work.
- **Do not add streak-shaming.** No flames, no "don't break the chain", no offer to restore a lost streak. Artboard 08 state 5 is the specification and it is deliberately flat.
- **Do not touch `dump/ledger.sql`** by hand. It is generated.
- If a decision is genuinely ambiguous, build the smaller version and put the question in `STATE.md`. Do not build both.

### Open questions — raise, do not answer alone

- Vanilla DOM vs Preact (decide session 12, record it).
- Whether `reference` stores a PDF path, and whether it points into a Zotero library or a plain folder.
- Whether The Wall includes unpublished drafts, and how they are marked.
- Whether `benefit_sharing.expires` should raise a warning in the app as the date approaches — it governs a real agreement, so probably yes, but not in v0.1.
