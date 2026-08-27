# The Deposit Ledger

A single-user, offline-first desktop application for logging daily research
work and building a medicinal-plant materia medica corpus. One SQLite file on
one Mac. No server, no account, no sync, no other user.

Records form one graph: a **daily entry** points at the **monograph** written
that day, which carries sourced **claims** citing **references**, which feed
the **outputs** published. The connectedness is the value — the system answers,
in one query, *which plants have I written about that have no human-trial
evidence and that I have never published on?*

The contract is `BUILD.md` (what it is, how it is built) and `DESIGN.md` (the
visual reference). `design/artboards.dc.html` is the final authority on
anything the two disagree about. `STATE.md` is where the build actually is,
session by session, including every open question.

---

## What is in the box

```
ledger/        the `ledger` CLI — Python 3.12, stdlib only
schema/        the four migrations; Python owns them and Rust never migrates
src/           the frontend — TypeScript, vanilla DOM, hand-written CSS
src-tauri/     the Rust core — rusqlite, and the window
design/        the artboards
dump/          where `just dump` writes the text file that gets committed
```

The database lives at `~/Documents/ledger.sqlite` unless `--db` or `LEDGER_DB`
says otherwise. It is never committed; `dump/ledger.sql` beside it is the
historical source of truth.

---

## Running it

### Once, per machine

On macOS you need the Xcode command line tools, and then four things:

```bash
xcode-select --install                       # the linker cargo needs
brew install just node python@3.12
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
cargo install tauri-cli --version '^2'       # a few minutes, once
```

### Then

```bash
just setup      # the virtualenv, npm install, and the development sidecar
just dev        # opens the window
```

`just dev` starts Vite itself, so it is the only command you need. It opens
against `~/Documents/ledger.sqlite`, creating and migrating it if it is not
there yet. Point it somewhere else to try things out without touching your real
ledger:

```bash
just dev /tmp/scratch.sqlite
```

The **app** never migrates — Python owns the schema (§3) — so what `just dev`
does is run `ledger migrate` for you before it opens the window, and say so.

`just setup` installs the CLI into the virtualenv, so you can put work into a
ledger from another terminal while the window is open. Both processes hold the
file at once; that is what WAL is for.

```bash
.venv/bin/ledger --db /tmp/scratch.sqlite log --minutes 90 --note "first day"
.venv/bin/ledger --db /tmp/scratch.sqlite mono "Khaya senegalensis" --part "stem bark" --no-edit
.venv/bin/ledger --db /tmp/scratch.sqlite win note "Evidence grading"
```

The window picks those up on ⌘R. To get `ledger` on your `PATH` proper,
`pipx install -e .` from the repo, or add `.venv/bin` to it.

**An empty ledger is not an empty screen.** Today shows the streak at 0 and
Corpus shows artboard 08's first-run state, which explains what a monograph is
and offers `ledger seed --from ~/notes/plants.csv`. There is no demo data and
there will not be: §8 forbids placeholder plants, and the species in the
artboards are design fixtures for artboard 01 only.

### Checks and hooks

```bash
just check      # ruff · pytest · cargo fmt · cargo clippy · cargo test · tsc
just hooks      # the pre-commit hook that keeps dump/ledger.sql current
```

Run `just hooks` once — `core.hooksPath` is local git config and cannot be
committed.

---

## The CLI

The terminal is usually already open, so most capture happens here.

```
ledger migrate                                    apply pending migrations
ledger log --minutes 90 --note "…" [--floor]      log a block of work
ledger mono "Khaya senegalensis" --part "bark"    open a monograph, edit in $EDITOR
ledger win note "Evidence grading" --url https://…  record an output
ledger ref 10.1016/j.jep.2019.112202              resolve a DOI against Crossref
ledger resolve [NAME] [--queue] [--accept]        resolve names against GBIF
ledger link ref DOI "Khaya senegalensis" --section indication
ledger seed --from ~/notes/plants.csv             open skeletons in bulk
ledger find "antimalarial bark"                   search everything
ledger dump [--to FILE]                           write the text dump
ledger restore --from FILE                        rebuild from a dump
```

Every enrichment subcommand takes `--json`. Network calls fail; when they do
the tool says so and keeps what it can — a DOI that Crossref would not answer
for is kept as an unresolved row and filled in on the next run.

---

## How it is put together

```
Tauri v2 window ── Rust core (rusqlite) ─┐
                                          ├── ~/Documents/ledger.sqlite  (WAL)
`ledger` — Python CLI ────────────────────┘
```

Both processes hold the database open at once. Every connection on both sides
sets `journal_mode=WAL`, `busy_timeout=5000` and `foreign_keys=ON`, and a test
proves the two write to one file without locking.

| Concern | Owner |
|---|---|
| Schema and migrations | **Python** — Rust reads `PRAGMA user_version` and refuses to start on a mismatch |
| Network enrichment (Crossref, GBIF) | **Python** — Rust has no HTTP client; the app calls the frozen CLI as a sidecar |
| UI reads and simple writes | **Rust** |
| Bulk import, seeding, dump/restore | **Python** |

Enrichment — name resolution, confidence thresholds, DOI normalisation — is
where bugs are expensive and silent, so it exists in exactly one language.
Where a rule has to exist in both (the streak, the search tokeniser, the claim
columns, the Crossref reply), a test asserts the two answers are equal rather
than each being equal to a literal.

---

## Two invariants, enforced in the database

**Sourcing.** `monograph.status` cannot become `reviewed` while any claim row
belonging to it has an empty source, and a `reviewed` record cannot take one
either. Ten triggers, and tests that prove they fire.

**Naming.** A name that GBIF matches below 0.90 is never written to
`accepted_name`. The record stays `skeleton` with its identifiers NULL, which
*is* the review queue.

The first of those has a visual half, and it is the most important rule in the
interface: a claim row with no source is tinted, marked on its leading edge,
and reads `⚠ source needed` — never blank. That count follows into the section
heading, the record header and the rail.

---

## Building a release

```bash
just freeze          # PyInstaller → src-tauri/binaries/ledger-<triple>
just verify-freeze   # prove it runs where there is no Python at all
just release         # check · freeze · npm build · cargo tauri build
```

`just freeze` bundles `schema/` into the binary, because the sidecar has to be
able to migrate on a machine that has never had Python.

---

## Tests that must never be deleted

`just check` runs ruff, pytest, `cargo fmt --check`, `cargo clippy -D
warnings`, `cargo test` and `tsc --noEmit`. Eight of those tests are named in
`BUILD.md` §7 and exist for reasons that are not obvious from reading them:

1. **Dump round-trip** — the committed text file is only the source of truth if
   it restores into an identical database.
2. **Concurrent access** — the app and the CLI writing to one file, both under
   WAL, neither locking.
3. **Migration ladder** — `000`→`003` from empty, with FTS triggers firing on
   insert, update **and** delete.
4. **Sourcing invariant** — in both directions.
5. **Name resolution** — a below-threshold match writes nothing.
6. **Crossref parsing** — against a fixture, never the live network. One live
   test is marked `@pytest.mark.network` and excluded.
7. **Streak** — no entries, one entry, gap yesterday, gap today, out of order.
8. **Gap queries** — never published on; cited by nothing.

---

## Licences

Fraunces and IBM Plex are SIL OFL 1.1; the licences sit beside the woff2 files
in `src/fonts/`. Nothing else is vendored.
