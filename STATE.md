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

---

## Plan health

The §1 scope reckoning still holds as written: v0.1 is five screens, light
theme only, monograph does not move. Session 01 revealed nothing that
contradicts it.
