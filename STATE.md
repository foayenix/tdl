# STATE.md — The Deposit Ledger

Where the build actually is. Updated at the end of every session (BUILD.md §0).

**Release target:** v0.1 — five screens, light theme only, by 5 Oct.
**Now:** week 1, foundation.

---

## Session log

### session 01 — the repo runs `just check` on an empty package

**Landed**

- Repo initialised on `claude/new-session-qjbps2`. `BUILD.md` and `DESIGN.md`
  committed as the contract; `design/artboards.dc.html` (+ `support.js`)
  committed as the final authority.
- `.gitignore` — the `.db` is excluded by name and by extension, per §4. `dump/`
  and `schema/` are tracked (both empty for now, held by `.gitkeep`).
- `justfile` with `check` (§7 order) and `venv`.
- Python package skeleton: `ledger/` with `__init__`, `__main__`, `cli.py`
  (argparse spine, no verbs yet), `ledger/tests/` with three CLI tests.
- `pyproject.toml` — no runtime dependencies. Declares the `ledger` console
  script, ruff config, and the `network` pytest marker that §7 test 6 needs
  so live-network tests stay out of `just check`.

`just check` passes: ruff clean, 3 tests green, cargo steps skipped (no crate yet).

**Deviations from the contract — deliberate, listed for review**

1. **`just check` skips the cargo steps while `src-tauri/` does not exist.**
   §7 lists four commands unconditionally, but the Rust crate does not arrive
   until session 12, and a `check` that cannot pass on day one is worse than
   one that reports what it ran. The guard is `[ -d src-tauri ]` — it turns
   itself off the moment session 12 lands. Revisit then.
2. **`just check` prefers `.venv/bin/python` over `python3`.** This container's
   `python3` is 3.11; BUILD.md §3 pins 3.12+. `just venv` builds a 3.12 venv
   with pytest and ruff. On the target Mac, where `python3` is already 3.12+,
   the fallback branch runs and `.venv` is never needed.
3. **No dependency added to the CLI itself.** pytest and ruff are dev tools
   named in §7; they are installed into `.venv`, never imported by `ledger/`.

**What is not here yet**

- `docs/spec.md` is referenced by BUILD.md §0 and §1 but was not supplied with
  the handoff. Nothing in session 01 needed it. It is wanted before session 09
  (the enrichment rationale) — ask for it.
- No `schema/`, no migrations, no database. Session 02.

**Environment notes (this container, not the Mac)**

- `sqlite3` CLI is **absent**. `just dump` (§4) shells out to it, and session 11
  depends on that. Python's `sqlite3` module can produce an identical dump via
  `Connection.iterdump()` if the CLI is unavailable — decide in session 11, do
  not pre-solve it.
- `just` is not packaged here; it was built from crates.io into `~/.cargo/bin`.

**Next session starts at:** BUILD.md §6, week 1, item **02** — `000_init.sql`
(`entry`, `monograph`, `reference`, `output`) plus `ledger migrate` stamping
`PRAGMA user_version`, plus the dump/restore round-trip test (§7 test 1).
Nothing before it is outstanding.

### session 02 — `ledger migrate` builds the four tables and a dump restores them

**Landed**

- `schema/000_init.sql` — `entry`, `monograph`, `reference`, `output`. Every
  field §4 calls out is present, including the easy-to-miss ones (`wfo_id`,
  `gbif_key`, `preparation`, `opened_count`, `why_it_mattered`, `read_state`).
- `ledger/db.py` — `connect()` opens WAL, `busy_timeout = 5000` and
  `foreign_keys = ON` on **every** connection, per §3. Default path
  `~/Documents/ledger.sqlite`, overridable with `--db`.
- `ledger/migrate.py` — discovers `schema/NNN_name.sql`, refuses a non-migration
  filename or a gap in the ladder, applies each file and stamps
  `user_version = NNN + 1` in one transaction. So 000→1 … 003→4 = schema v4.
- `ledger/commands/migrate.py` + `ledger migrate`. Idempotent: a second run
  prints `nothing to apply · schema v1`.
- **§7 test 1, dump round-trip** — populate all four tables, dump, restore into
  a fresh file, assert `sqlite_master` and every row identical. Plus the
  migration-ladder assertions (§7 test 3, as far as the migrations that exist)
  and CHECK-constraint tests for the three enums.

`just check` passes: ruff clean, 23 tests green.

**Decisions taken, smaller version built**

1. **`foreign_keys = ON` is a fourth pragma** §3 does not name. Without it the
   `output.entry_id` reference is decorative. It is per-connection, so **the
   Rust side must set it too** — session 12.
2. **The dump is `Connection.iterdump()`, not the `sqlite3` CLI.** §4 writes the
   habit as `sqlite3 ledger.sqlite .dump`; the test must run wherever pytest
   runs, and this container has no `sqlite3` binary. `just dump` (session 11)
   still has to decide which one ships. `iterdump` does not carry
   `user_version`, so whatever session 11 writes must stamp it alongside — the
   test does this explicitly and says so.
3. **No indexes beyond the two UNIQUE constraints.** At forty records they buy
   nothing and they are cheap to add in a later migration.
4. **A reference with neither DOI nor ISBN is allowed.** §4 says "`doi` *or*
   `isbn`", which reads as the field pair rather than a constraint, and a field
   notebook has neither. No CHECK — see the open question below.
5. **`monograph` has no `entry_id`.** §2 says a daily entry points at the
   monograph written that day, but §4's field list has no such column and
   session 05 puts `entry_id` on `output` only. `monograph.first_written` dates
   it. See the open question below.

**Next session starts at:** BUILD.md §6, week 1, item **03** — `ledger log`,
writes an entry, prints the streak. §7 test 7 (streak query: no entries, one
entry, gap yesterday, gap today, out of order) belongs to that session.

### session 03 — `ledger log` writes a day and prints the streak

**Landed**

- `ledger/entries.py` — `log()`, `run_length()`, `current_streak()`,
  `FLOOR_MINUTES = 20`.
- `ledger log --minutes 90 --note "…" [--date YYYY-MM-DD] [--floor]`, printing
  `2026-08-27 · thursday · 45 min · streak 6 days`.
- **§7 test 7, streak query** — all five cases named in §7 plus a broken run, a
  run before a gap, and a lone entry ninety days back.

`just check` passes: ruff clean, 36 tests green.

**The streak needed one decision the contract does not settle**

§4's query returns the length of the most recent unbroken run. Artboard 08
state 5 says a run broken by three days reads **0**, not 41 — so the raw query
alone contradicts the artboard, and the artboards win. `current_streak()` runs
§4's SQL **verbatim** and returns 0 when the run no longer reaches today or
yesterday.

The one-day grace is mine: without it the streak reads 0 every morning before
the first block is logged, which is exactly the shaming §8 forbids. Flagged
below.

**Also decided**

- **Minutes accumulate, notes append.** `ledger log` records a *block*, and a
  day usually holds more than one; artboard 02's single note is the in-app
  autosaving field editing the same row. `--floor` sticks until changed.
- `--date` is validated before the database is opened, so a typo cannot create
  a file.

**Next session starts at:** BUILD.md §6, week 1, item **04** — `ledger mono`:
skeleton, `$EDITOR` template, status transitions. Note that the sourcing
invariant guarding `reviewed` is session 06 (it needs the claim tables), so 04
can only enforce the ordering of the four statuses, not the invariant.

---

## Open questions

Carried from BUILD.md §8, plus what sessions have added. Raise these; do not
answer them alone.

- Vanilla DOM vs Preact — decide session 12, record the answer here.
- Whether `reference` stores a PDF path, and whether it points into a Zotero
  library or a plain folder.
- Whether The Wall includes unpublished drafts, and how they are marked.
- Whether `benefit_sharing.expires` warns in-app as the date approaches.
- **New (01):** `docs/spec.md` is missing from the handoff — is it still the
  live document, or has BUILD.md replaced it?

- **New (02):** should `reference` refuse a row with neither DOI nor ISBN? §4
  reads either way and a field notebook has neither. Currently allowed.
- **New (02):** how does a daily entry point at the monograph written that day —
  `monograph.entry_id`, or the join on `first_written`? Built as the join.
- **New (02):** is `entry.floor_day` the user's deliberate "today was a floor
  day" mark, or is it derived from `minutes >= 20`? Artboard 02 shows both a
  yes/no toggle and a derived `floor met 118 / 140`. Stored as an explicit flag;
  the derived count can stay derived.

- **New (03):** is one day of grace right before the streak reads 0? Logged
  yesterday but not yet today currently keeps the run live. Artboard 08 only
  specifies the three-day case. If it should be strict, `current_streak()` is
  the one line to change.

---

## Plan health

The §1 scope reckoning still holds as written: v0.1 is five screens, light
theme only, monograph does not move. Session 01 revealed nothing that
contradicts it.
