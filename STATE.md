# STATE.md — The Deposit Ledger

Where the build actually is. Updated at the end of every session (BUILD.md §0).

**Release target:** v0.1 — five screens, light theme only, by 5 Oct.
**Now:** week 3, shell and components — item 15 next.

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

1. ~~**`just check` skips the cargo steps while `src-tauri/` does not exist.**~~
   **Resolved in session 12**: the crate exists, the guard is gone, and all four
   §7 commands now run unconditionally and in order.
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

### session 04 — `ledger mono` opens a skeleton and edits it in `$EDITOR`

**Landed**

- `ledger/monographs.py` — `create()`, `by_name()`, `update()`, `set_status()`,
  `render_template()`, `parse_template()`.
- `ledger/editor.py` — hands text to `$EDITOR`, returns None when nothing changed.
- `ledger mono NAME [--part --family --authority --habitat] [--status S] [--no-edit]`.
- Rewriting the summary stamps `summary_rewritten_at`; writing the *same* text
  again does not. Every write touches `last_touched`.
- 17 tests: skeleton creation, the four transitions, and a full round trip
  through the template including multi-paragraph prose.

`just check` passes: ruff clean, 53 tests green.

**Invariant 2, read carefully**

"Never let an unresolved name into `accepted_name`" guards against a
**below-threshold GBIF match** being written there — not against the
researcher's own typing. Artboard 08 state 4 offers `Enter name by hand` as a
resolution, so a hand-entered name is a resolved name. `ledger mono` therefore
writes the typed name straight into `accepted_name` and leaves `wfo_id`,
`gbif_key` and `gbif_confidence` NULL.

That NULL **is** the review queue: `status = 'skeleton' AND gbif_key IS NULL`
is artboard 08's `queue 3 of 7` with no extra table, and the candidate list it
shows can be fetched live at review time rather than stored. Session 09 should
confirm this before building anything else — there is no fifth migration slot
in schema v4 if it turns out candidates must persist.

**The template format**

```
# Khaya senegalensis
authority: (Desr.) A.Juss.
family: Meliaceae
part: stem bark
habitat: African mahogany, dry-savanna belt

## summary
…prose…

## preparation
…prose…
```

Deterministic to parse, and it refuses an invented field or section rather than
silently dropping it. The `# name` line is fixed — renaming is a resolver's job.
Claim rows (vernacular, indication, constituent, safety) are **not** in the
template; they are per-row with per-row sourcing and arrive in session 06.

**Not enforced here:** the sourcing invariant. `--status reviewed` currently
succeeds on any record, because the trigger that blocks it needs the claim
tables. Session 06 lands the trigger and §7 test 4 with it.

**Next session starts at:** BUILD.md §6, week 1, item **05** — `ledger win`,
an output linked to today's entry.

### session 05 — `ledger win` records an output against today's entry

**Landed**

- `ledger/outputs.py` — `record()`, `entry_for()`, `counts_by_kind()`, `total()`.
- `ledger win KIND TITLE [--venue --url --date]`, printing the output and the
  running wall count.
- `counts_by_kind()` returns every kind including the empty ones, in ramp
  order — artboard 04's header counts show all five whether or not they have
  rows, and a zero is a real number there.
- 9 tests.

`just check` passes: ruff clean, 62 tests green.

**Two dates, not one**

`--date` is when the output *went out*; the entry it attaches to is **today**,
the day it was deposited. A paper published in June does not retroactively make
June a day worked, and artboard 02 says "deposit — attach to today". Recording
one on an unlogged day opens that day at 0 minutes, because depositing is work
and the alternative is an output hanging off nothing.

That 0-minute day counts toward the streak. It is under the 20-minute floor, so
it will not count toward `floor met` — which reads correctly: a day that
happened, below the floor.

**Not here yet:** the plant link. Artboard 04 shows `plants` on every card and
`whole corpus` / `method, no plant` where there is none; that is
`output_monograph` in `002_links.sql`, session 07.

**Week 1 is complete.** The five foundation items are ticked and the daily loop
exists in the CLI: log a day, open a monograph, record a win.

**Next session starts at:** BUILD.md §6, week 2, item **06** — `001_claims.sql`
(`vernacular`, `indication`, `constituent`, `safety`, `benefit_sharing`), the
sourcing trigger, and §7 test 4. This is the session that finally makes
`--status reviewed` refuse an unsourced record.

### session 06 — the claim tables, and `reviewed` now refuses an unsourced record

**Landed**

- `schema/001_claims.sql` → `user_version = 2`. `vernacular`, `indication`,
  `constituent`, `safety`, `benefit_sharing`, all cascading from `monograph`.
- **Source is two columns, not one.** §4 says a source is "a `reference_id`, or
  free text for a field record", so it is `source_reference_id` (a real foreign
  key) plus `source_note`. One TEXT column holding `"R7"` would have thrown away
  the graph, and the graph is the whole value.
- `CREATE VIEW unsourced_claim` — every unsourced row in the database with the
  record it holds back. The triggers read it and so does every count the UI
  shows, so "unsourced" is defined once.
- **Invariant 1 as a wall, not a doorway.** Ten triggers: two stop a record
  reaching `reviewed` over unsourced rows, and eight stop an unsourced row being
  added to — or un-sourced within — a record that is already `reviewed`. §4 says
  "a trigger"; one trigger leaves the record mendable from the other side, and
  an invariant with a hole is not an invariant.
- `ledger/claims.py` — `add()`, `set_source()`, `Source`, the E1–E6 codes, the
  four-step ramp, `headline_evidence()` (max across indications),
  `unsourced_by_table()` for the per-section counts.
- **§7 test 4** across all four claim tables in both directions, plus 19 more.

`just check` passes: ruff clean, 104 tests green.

**A bug in session 02's dump, found by extending its own test**

The round-trip fixture now writes rows into all nine tables, including a
deliberately unsourced one. That broke the restore, and the reason matters:

`Connection.iterdump()` emits tables **alphabetically**, so `benefit_sharing`
and `constituent` restore before `monograph` exists. The foreign keys fail, and
worse, the sourcing triggers' `SELECT status FROM monograph` fails too.

`ledger/dump.py` replaces it and emits **creation order** — every parent before
its children, all indexes/views/triggers last, after the data they would
otherwise fire on. It also carries `PRAGMA user_version`, which `iterdump`
drops; without it a restored file cannot tell the Rust core which schema it is.
The test now restores with foreign keys **on** and asserts
`PRAGMA foreign_key_check` comes back empty.

**Session 11 inherits this**: `just dump` must use `ledger dump`, not
`sqlite3 .dump`. The CLI has the same alphabetical hazard and this container
has no `sqlite3` binary anyway. That is a change to §4's stated habit and wants
a decision.

**Next session starts at:** BUILD.md §6, week 2, item **07** — `002_links.sql`
(`monograph_reference` with `section`, `output_monograph`, `reference_tag`,
`inbox_line`) plus `ledger link` and `ledger seed`.

### session 07 — the graph has edges: `ledger link` and `ledger seed`

**Landed**

- `schema/002_links.sql` → `user_version = 3`. `monograph_reference` (with
  `section`), `output_monograph`, `reference_tag`, `inbox_line`.
- `ledger/links.py` — `bind_reference()`, `bind_output()`, `tag()`, and **both
  gap queries from §4 verbatim**: `never_published_on()` and
  `cited_by_nothing()`.
- `ledger link ref DOI|ID NAME [--section]` · `ledger link output ID NAME` ·
  `ledger link tag DOI|ID TAG`. Binding twice is reported, not an error.
- `ledger/seed.py` + `ledger seed --from FILE [--dry-run]`. Reads `name` plus
  four optional columns, accepts the header names the `$EDITOR` template writes
  so a seed file round-trips, ignores columns it does not know, and never
  touches a plant already in the corpus.
- **§7 test 8, gap queries** — a record with an output does not appear, one
  without does; a reference bound to nothing appears in `cited by nothing`.

`just check` passes: ruff clean, 133 tests green.

**The round-trip test caught its own gap**

The assertion added in session 06 — "a table was left empty; the round trip
does not prove anything about it" — failed the moment 002 landed four new
tables. That is the assertion working. The fixture now writes into all
thirteen tables, including an unclassified `inbox_line` with `kind` NULL.

**Decisions**

- **`ledger seed` is not the general importer §5 forbids.** Five known columns
  and a `name` requirement. Anything else stays a throwaway script.
- `section` on `monograph_reference` is nullable — bound but not yet placed is
  a real state — and CHECKed against the record's seven sections when set. The
  unique key includes `section`, so one reference can be cited in two sections
  of the same record, which artboard 05 shows.
- `inbox_line` is `UNIQUE (captured_at, raw)`, so re-running `ledger inbox`
  over the same file cannot double-route a line.

**Next session starts at:** BUILD.md §6, week 2, item **08** — `ledger ref` +
Crossref, `--json`, DOI normalisation, offline failure path. §7 test 6 wants a
recorded fixture for the parsing test and exactly one live test marked
`@pytest.mark.network`, which `pyproject.toml` already excludes from
`just check`.

### session 08 — `ledger ref` resolves a DOI, and survives not being able to

**Landed**

- `ledger/crossref.py` — `normalise_doi()`, `fetch()`, `parse()`, `lookup()`,
  and three named failure modes: `NotFound`, `Offline`, `CrossrefError`. A DOI
  that does not exist and a network that does not answer are different events
  and the tool says which.
- `ledger/references.py` — `save()`, `record_unresolved()`, `cite()`,
  `counts_by_read_state()`.
- `ledger ref DOI [--json] [--timeout]`.
- 45 tests. `just check` passes: ruff clean, 178 green, 1 deselected (network).

**DOI normalisation**

Nine paste shapes land on one string: resolver prefixes (`https://doi.org/`,
`dx.doi.org`, `doi:`), surrounding whitespace, a trailing full stop from prose,
and **case**. DOIs are case-insensitive, so two casings of one DOI would be two
rows for one paper. A malformed DOI is refused **before** the network is
touched, and there is a test that fails if that ever stops being true.

**The offline path, verified for real**

Crossref is unreachable from this container (see below), so the failure path
was exercised against a genuinely dead network rather than a mock:

```
R1 · 10.1016/j.jep.2019.112202
10.1016/j.jep.2019.112202 · queued
could not reach Crossref: … 403 Forbidden — kept as unresolved, run again later
```

The DOI is kept with `added_from = 'offline'` and `title` set to the DOI
itself. Losing a paste because Crossref was down is the capture friction §5
says kills systems like this. Running `ledger ref` on the same DOI later fills
the row in — **but only while it is still marked `offline`**. A row whose title
was corrected by hand is never clobbered by a retry; there is a test for that.

**§7 test 6 is landed but its fixture is not a recording — this needs you**

`api.crossref.org` is refused by this environment's egress proxy: 403 to the
CONNECT, which is an organisation policy denial, not a transient failure. So
there is no way to record a real response here, and inventing a paper and a DOI
is precisely what §8 forbids.

`fixtures/crossref_shape.json` therefore uses Crossref's own **`10.5555` test
prefix** and strings that read `PLACEHOLDER`, and it exercises the response
*shape* — the title/container-title arrays, the author list, the
`issued.date-parts` fallback chain. `fixtures/README.md` carries the one curl
command that replaces it. The live test is written, marked
`@pytest.mark.network`, and excluded from `just check`; running
`pytest -m network ledger/tests` on the Mac both proves the parser against the
real API and is the quickest way to capture the recording.

**`access` is left NULL.** Crossref has no dependable open/closed field.
Deriving one from the licence block would put a wrong answer in a record that
gets cited, which is the failure §4 warns about for names. The library's
metadata table shows `access`; where it comes from is an open question.

**Next session starts at:** BUILD.md §6, week 2, item **09** — the GBIF
resolver, the 0.90 confidence threshold and the review queue, with §7 test 5.
Session 04 left a question there: whether artboard 08 state 4's candidate list
must persist. **GBIF is likely blocked by the same policy as Crossref** — check
first, and expect to land the resolver with a shape fixture the same way.

### session 09 — the GBIF resolver, the 0.90 threshold, and the review queue

**Landed**

- `ledger/gbif.py` — `match()`, `parse()`, `Match`, `CONFIDENCE_THRESHOLD = 0.90`.
  GBIF scores 0–100; everything else in the design talks 0–1, so it converts on
  the way in and `confidence 0.42` means what the artboard says it means.
- `ledger/naming.py` — `queue()`, `resolve()`, `accept()`.
- `ledger resolve [NAME] [--queue] [--accept] [--threshold] [--json]`.
- **§7 test 5** plus 22 more.

`just check` passes: ruff clean, 201 green, 2 deselected (network).

**Session 04's question is answered: the queue needs no table**

`status = 'skeleton' AND gbif_key IS NULL` **is** artboard 08's `queue 3 of 7`,
and it comes out ordered by `first_written` for free. Candidates are carried on
the `Resolution` object and rendered at review time; nothing about state 4
needs them persisted. There is no fifth migration in schema v4 and now nothing
wants one.

`checked 2026-08-24 09:12` on state 4 is `last_touched`, which a refusal
stamps. No new column.

**What a refusal does and does not do**

A below-threshold match writes `gbif_confidence` **and nothing else**.
`accepted_name` is untouched, `gbif_key` stays NULL, `status` stays `skeleton`
— which is what keeps it in the queue. `matchType: NONE` comes back with
`confidence: 100` from GBIF, and `is_a_match` refuses it regardless; there is a
test for that, because trusting that number would be the silent-name-bug §4
warns about.

Two more deliberate limits:

- **A lookup never overwrites what you typed.** `family` and `authority` fill
  blanks only.
- **Resolving a name does not move `status`.** A confirmed binomial says
  nothing about how written the record is.
- `--accept` takes a match below the threshold, because artboard 08 state 4
  offers exactly that. A person deciding is not the machine guessing.

**Same fixture caveat as session 08.** `api.gbif.org` is refused by the same
policy (403 on CONNECT). `gbif_shape_high.json` uses the `usageKey 3190368`,
family and authority **artboard 05 itself states**; `gbif_shape_low.json` uses
the artboard's own `0.42` and three candidates, with `PLACEHOLDER` names
because guessing at synonymy would be inventing botany. `fixtures/README.md`
has the curl commands; the live test is marked `@pytest.mark.network`.

**The plan has a hole: nothing resolves `wfo_id`**

§3 names WFO alongside Crossref and GBIF, and invariant 2 says plainly *"Store
the WFO-ID as well as the name — names change, IDs do not"*. `monograph.wfo_id`
exists and artboard 05 displays it. **No session in §6 fills it.** Session 09 is
GBIF only, and I have not quietly extended it.

As things stand `wfo_id` is NULL for every record through v0.1, and artboard 05's
identity strip renders a blank. That either needs a session or an explicit
decision to ship without it. Raising, not answering.

**Next session starts at:** BUILD.md §6, week 2, item **10** — `003_fts.sql`,
FTS5 with sync triggers on insert, update **and** delete, and `ledger find`.
That takes the schema to v4.

### session 10 — schema v4: FTS5, its sync triggers, and `ledger find`

**Landed**

- `schema/003_fts.sql` → **`user_version = 4`**, the version artboard 08's
  footer shows. One `search` virtual table, 22 triggers, and a backfill so the
  migration works on a database that already has records.
- `ledger/find.py` — `find()`, `to_match()`, `nearest()`, `corpus_size()`.
- `ledger find QUERY [--limit] [--json]`, printing artboard 08 state 6's line
  word for word when nothing matches, with the nearest name and its edit
  distance.
- 31 tests here, and §7 test 3's FTS half is now real.

`just check` passes: ruff clean, 233 green, 2 deselected (network).

**Claim rows are indexed as themselves**

`search` carries `kind`, `row_id` and `monograph_id`. An indication, a
vernacular name, a compound or a safety finding is its own row pointing back at
its plant. The alternative — folding claim text into the monograph's index
entry — means rebuilding that entry every time any claim changes, and 22 simple
triggers are easier to be sure of than 7 clever ones. `Results.monograph_ids`
folds the hits back onto plants, so one plant hit through three claims is
listed once.

`ledger find "antimalarial bark"` therefore works, which it would not have if
only monograph prose were indexed.

**The delete half, which is the half that rots**

Every indexed table has insert, update **and** delete triggers, and each has its
own test. One extra: `ON DELETE CASCADE` does **not** fire per-row delete
triggers unless `recursive_triggers` is on, and that pragma is per-connection —
so deleting a record would have left its claim rows in the index for any
connection that forgot it. `search_monograph_sweep` clears them at the record
level instead, where it holds however the caller opened the database. There is
a test that deletes a record with two claims and asserts the index is empty.

**Query text is quoted, never parsed**

`to_match()` tokenises and quotes: `bark"`, `10.1016/j.jep`, `NEAR(a b)` and
`a OR b` are searched for, not executed as FTS5 syntax. Tokenizer is
`unicode61 remove_diacritics 2`, so `cailcedrat` finds `caïlcédrat`.

**Second bug in the dump, same test caught it**

FTS5's shadow tables (`search_data`, `search_idx`, …) come into existence with
`CREATE VIRTUAL TABLE`; replaying their own `CREATE TABLE` statements fails, and
dumping their contents would double-write the index.

`ledger/dump.py` now excludes every virtual table and its shadows, keeping only
the `CREATE VIRTUAL TABLE` statement — **the index is derived data and the dump
holds truth.** `restore()` rebuilds it by running a no-op `UPDATE t SET id = id`
over each indexed table, which fires the sync triggers. That deliberately
avoids restating the trigger bodies in Python: two definitions of "indexed"
would drift, and the triggers are the one that matters.

**Week 2 is complete.** The corpus is in the database and every §7 test that
does not need the Rust core exists: 1 (dump round-trip), 3 (migration ladder,
now reaching v4 with FTS triggers), 4 (sourcing), 5 (name resolution),
6 (Crossref, with the fixture caveat), 7 (streak), 8 (gap queries). Only
**§7 test 2, concurrent access**, is outstanding — it needs the Rust side, so
it belongs to session 12.

**Next session starts at:** BUILD.md §6, week 2, item **11** — `just dump` + a
pre-commit hook, and the restore-from-any-commit test. Sessions 06 and 10 have
already decided what `just dump` must call; this session is the plumbing.

### session 11 — `just dump`, the pre-commit hook, and restore from any commit

**Landed**

- `ledger dump [--to FILE|-]` and `ledger restore --from FILE [--force]`.
  `restore` refuses to overwrite an existing database without `--force`, and
  reports `PRAGMA foreign_key_check` rather than claiming success over a broken
  file.
- `just dump` · `just restore` · `just hooks`.
- `.githooks/pre-commit` — regenerates `dump/ledger.sql` and stages it. Quiet
  and non-blocking: no database, nothing to do, exit 0. Reads `LEDGER_DB` so it
  works for a database somewhere other than `~/Documents`.
- `test_restore_from_commit.py` — walks every commit that touched
  `dump/ledger.sql`, restores each into a fresh file, and checks foreign keys,
  `user_version` and the four core tables.

`just check` passes: ruff clean, 242 green, 2 skipped (no dump in history
yet, with the reason printed), 2 deselected (network).

**Run `just hooks` once.** It sets `core.hooksPath`, which is local git config
and cannot be committed. Until it is run the dump is only refreshed when you
run `just dump` by hand.

**The history walk has nothing to walk yet, and says so**

There are no commits carrying `dump/ledger.sql` — the git habit starts with
your first real `just dump`. The parametrised test therefore has an empty
parameter set, and a companion test **skips with the reason spelled out**
rather than passing quietly. A green test over zero cases is how a check stops
being a check.

The mechanism itself is proven two other ways: a test that dumps and restores
through the identical code path without needing history, and — during this
session — a throwaway repo with two commits, both restored from
`git show <sha>:dump/ledger.sql` at schema v4 with the index rebuilt.

**Nothing fabricated was committed.** `dump/ledger.sql` stays absent. Writing a
dump of invented plants into the file that is meant to be your historical
record would poison exactly the thing §8 protects.

**§4's stated habit has changed, and this is the confirmation to give or refuse**

```
sqlite3 ledger.sqlite .dump > dump/ledger.sql     # §4 as written
just dump                                          # what now happens
```

`sqlite3 .dump` cannot restore this schema — sessions 06 and 10 have the
detail: alphabetical table order breaks the foreign keys and the sourcing
triggers, and FTS5's shadow tables cannot be replayed at all. `just dump` calls
`ledger dump`, and `sqlite3 new.db < dump/ledger.sql` will restore the data but
leave the **search index empty**; `ledger restore` rebuilds it. If §4 should be
amended, the wording to change is in "The git habit".

**Week 2 is complete.**

**Next session starts at:** BUILD.md §6, week 3, item **12** — `cargo tauri
init`, the window, the WAL connection, the `user_version` guard, and the
vanilla-vs-Preact decision. §7 test 2 (concurrent access) belongs there, and it
is the last §7 test outstanding. Note for that session: `foreign_keys = ON` is
per-connection and the Rust side must set it (session 02), and so must
`busy_timeout`.

### session 12 — the window opens, and both processes write to one file

**Landed**

- `src-tauri/` — Tauri v2 crate, **compiled and tested**, not just written.
  `src/lib.rs` is the core with no Tauri in it: `open()` (WAL,
  `busy_timeout = 5000`, `foreign_keys = ON`), `user_version()`,
  `open_checked()` and its errors, `status()`.
- `src/main.rs` — the window, 1440 × 1024 to match the artboards, one
  `ledger_status` command. `capabilities/default.json` grants
  `shell:allow-execute` for the sidecar and nothing else; the frontend holds no
  shell permission, exactly as §3 requires.
- **§7 test 2, concurrent access** — an open Rust connection and ten `ledger`
  subprocess writes interleaved against one file, with the app reading back
  each CLI write. No `database is locked`. Plus five more Rust tests: the
  pragmas, the schema guard both ways, a missing file, and the sourcing
  invariant holding against the Rust side too.
- Frontend: Vite + TypeScript, `src/index.html`, `src/ledger.ts`, `src/main.ts`.
  The window currently shows the path, the size and `schema v4` — that is the
  whole of session 12's screen, and it proves the connection is real.

`just check` passes end to end in about six seconds: ruff, 242 pytest, cargo
fmt, cargo clippy `-D warnings` on all targets, 6 cargo tests, `tsc --noEmit`.

**Every §7 test now exists.** Test 2 was the last one outstanding.

**The decision this session owed: vanilla DOM, not Preact**

The five v0.1 screens are document-shaped, not app-shaped — dense tables and a
long record, rendered from a query. The interactive parts are a filter rail
whose state lives in the URL hash, an autosaving note, and inline row adds.
None of that needs a VDOM, and every other line of §3 pushes the same way: no
React, no Tailwind, no component library, hand-written CSS. Vanilla keeps the
dependency count at one.

If session 24's inline row editing turns into a mess, that is the moment to
revisit — Preact is a one-file change to the render layer, not a rewrite.

**Three additions to record**

1. **`@tauri-apps/api`** is a new dependency. It replaces reaching for
   `window.__TAURI__`, which needs `withGlobalTauri` and gives up type safety
   at the one boundary where the frontend talks to Rust. `vite` and
   `typescript` are the build, named in §3.
2. **`just check` now also runs `tsc --noEmit`** — a fifth command §7 does not
   list. From session 13 on the frontend is the work, and without it nothing
   checks it. The four §7 commands run first, in order, unchanged.
3. **`just sidecar`** writes a development stand-in at
   `src-tauri/binaries/ledger-<triple>` — a two-line shim that runs the CLI
   from source. `tauri.conf.json` declares `externalBin` as §3 shows, so
   *every* cargo invocation needs that file to exist, and the real one is a
   PyInstaller freeze that does not arrive until session 30. `check` creates it
   if it is missing.

**Two things are placeholders, deliberately**

- **The icons are flat `#14705B` squares.** An icon is artwork, not
  infrastructure; inventing one would be inventing branding. `generate_context!`
  will not compile without it.
- **`cargo tauri` CLI is not installed here**, so the scaffold was written by
  hand rather than by `cargo tauri init`. The layout is the standard one and
  the crate builds. Session 30 needs the CLI for `cargo tauri build`.

**Environment note.** Tauri needs `libwebkit2gtk-4.1-dev` on Linux; it was
missing and is now installed in this container. On the target Mac none of that
applies. The Rust core itself has no Tauri in it, so it would have compiled
and tested either way — that separation is worth keeping.

**Next session starts at:** BUILD.md §6, week 3, item **13** — artboard 01,
every token in `DESIGN.md` §1 as a CSS variable, fonts self-hosted as woff2 in
`src/fonts/`. **Fraunces and IBM Plex are SIL OFL and are fetched from Google
Fonts, which this container is policy-blocked from** — expect the same
situation as Crossref and GBIF, and expect to have to check whether the font
files can be obtained at all before writing CSS against them.

### session 13 — every token is a CSS variable, and DESIGN.md is now executable

**Landed**

- `src/styles/tokens.css` — **every** value in DESIGN.md §1, §2, §3 and §5 as a
  custom property. Both themes, transcribed literally, nothing computed.
- `src/styles/fonts.css` — 14 `@font-face` declarations, all local.
- `src/fonts/` — the woff2 files, both licences, and a README saying which cuts
  are here and why.
- `src/styles/base.css` — the eleven type roles from §2 as classes, plus
  `.binomial` / `.authority`, the focus ring, and the ground.
- `ledger/tests/test_design_tokens.py` — 37 tests.

`just check` passes: 279 pytest, 6 cargo, tsc clean.

**The token test is the point of this session**

It reads `DESIGN.md` and `tokens.css` and compares them:

- every row of §1's table is declared, in **both** themes, with exactly the hex
  it states;
- **every hex in `tokens.css` appears somewhere in `DESIGN.md`** — this is the
  "do not derive a colour" guardrail as an assertion, and it fails on an
  invented value rather than on review;
- no `lighten(`, `darken(`, `color-mix(`, `filter:` or `invert(` in either
  block, so the dark theme cannot quietly become a computed one;
- the radius scale is exactly {2, 3, 4, 5};
- the spacing scale is the twelve steps §3 lists, and 6, 7, 14, 18 are asserted
  present — artboard 01's "8px grid" caption is wrong and this stops anyone
  acting on it;
- no `box-shadow`, no `gradient(` in any stylesheet.

It caught its own author immediately: the first run failed because `base.css`
carries a comment reading "No box-shadows anywhere". Comments are stripped now.

**The dark tokens are transcribed although v0.1 is light only**

They are inert — nothing sets `data-theme` — but keeping both halves of §1 in
one file means session 28's dark work is a class flip rather than a second trip
through DESIGN.md, and it lets the test check both columns of the table now,
while the transcription is fresh. This is transcription, not implementation;
§1's freeze on dark theme is intact.

**Fonts: obtainable after all**

Google Fonts is policy-blocked here, like Crossref and GBIF. The families are
all SIL OFL and the `@fontsource` npm packages redistribute the upstream
releases, and **npm is reachable** — so the woff2 files were vendored from
there and checked in. `@fontsource` is **not** a dependency; the files are in
the tree, which is what self-hosted means.

Only the cuts §2 actually asks for: Fraunces 600 normal and italic; Plex Sans
400, 500, 600 and 400 italic; Plex Mono 400. `latin` **and** `latin-ext` for
each — `latin-ext` is not optional here, because vernacular names and authority
strings carry diacritics that plain `latin` drops. 296 KB in total. Adding a cut
means a line in DESIGN.md §2 first.

**Next session starts at:** BUILD.md §6, week 3, item **14** — artboard 01's
component specimens with all five states (§4 of DESIGN.md): buttons primary and
quiet, nav item, checkbox, keycap. A dash in the artboard means the state does
not apply.

### session 14 — artboard 01's component specimens, all five states

**Landed**

- `src/styles/components.css` — button primary, button quiet, the `secondary`
  "Draft with model" variant, nav item, checkbox, keycap, the text field, and
  every chip family in DESIGN.md §5.
- `src/dom.ts` — `el`, `append`, `clear`, `binomial`. Four helpers; that is the
  whole of the vanilla-DOM decision made in session 12.
- `src/screens/system.ts` — artboard 01 rendered live from the CSS variables:
  colour swatches, the type ramp, the state grids, the chips.
- `src/styles/screens.css` — the specimen layout and the app shell.

`just check` passes: 281 pytest, 6 cargo, tsc clean.

**Screenshot compared against artboard 01 — §7's manual check**

Every difference, and what was done about it:

| difference | resolution |
|---|---|
| Hover and focus columns first rendered as *default* — a pointer can only be in one place, so a live `:hover` cannot fill a specimen table | **Fixed.** Every hover/focus rule is now written against both the pseudo-class and an `.is-hover` / `.is-focus` class. The artboard shows all five states at once and now so does the screen. The classes are for artboard 01 and nothing else, and the comment in `components.css` says so. |
| Type-ramp spec column wrapped `PLEX MONO 400 / 10 · .14EM` onto two lines | **Fixed** — column widened 168 → 196px. |
| Artboard's right-hand caption reads `8px grid · 4px radius max · hairline #DEE1DB` | **Deliberately omitted.** DESIGN.md §3 states that caption is wrong: the real scale includes 6, 7, 14 and 18. Rendering it would put a known-false statement on the screen, and rewriting it would be inventing copy. |
| Artboard 01 also carries `table row — monograph`, `reference row` and `output card` specimens | **Deferred, not dropped.** The table primitive is session 16, the reference row session 27, the output card session 29. They will be added to this screen as they land. |
| The footer shows a raw `TypeError … reading 'invoke'` in a plain browser | **Correct, not a bug.** `invoke` only exists inside the Tauri window. The screenshot was taken from `vite preview`; in the app the footer reads the path, size and schema. The error path is the same one artboard 08 state 1 needs. |

Everything else matched: all three families render from the local woff2, the
binomial is italic with the authority upright, the evidence ramp collapses six
levels onto four steps with the polarity flip at E5/E6, and the nav item's
selected state carries the fill, the bar, the 500-weight label and the primary
count.

**DESIGN.md was wrong in three places. I have amended it, as §5 of that file
instructs — the artboards win, fix the file, note it here.**

1. **Nav item.** DESIGN.md said "Selected turns both label and count `primary`
   — **it does not add a fill or a bar**". Both artboard 10's specimen row and
   artboard 02's real left nav add a `primary-wash` fill **and** a 2px `primary`
   left bar, and set the label to weight 500. It also gave the default count as
   `ink`; the artboards use `muted`.
2. **Checkbox.** DESIGN.md said 12px; both artboards are **11px**. The hover
   ring (`#8A938D` light, `#7A8781` dark) was not recorded in DESIGN.md at all —
   it is now, which is also what lets the token test keep passing.
3. **Keycap.** DESIGN.md said selected "inverts to `primary` fill with
   near-black text". That is the **dark theme only** — the light artboard is
   `#FFFFFF` on `#14705B`. It is the same polarity flip the evidence ramp makes
   at step 3: near-black text belongs where the accent is bright.

Each amendment carries a `> Corrected in session 14` note in DESIGN.md itself,
so the next reader sees why the file changed.

**Artboard 01's species are used here and only here.** §8 permits it in exactly
these words: "design fixtures for artboard 01 only — never seed data". Nothing
in the specimen screen touches the database.

**Next session starts at:** BUILD.md §6, week 3, item **15** — the left nav
with live counts and the real footer (path, size, last write). The nav item
component is built; session 15 is the sidebar around it, the section labels
(`ledger` / `catalogue` / `public` / `system`, Plex Mono 9 · .14em in the
artboard — another size §2 does not list), and Rust commands for the counts.

### session 16 — the table primitive, and the unsourced row

**Landed**

- `src/table.ts` — `renderTable()`, `sourceCell()`, `markerColumn()`, and
  `COLUMNS`: all four width tables from DESIGN.md §7, transcribed verbatim.
  "Use them; do not let content decide" is enforced by setting
  `grid-template-columns` from the percentages with no gap — the gutters are
  cell padding, so the percentages stay percentages of the inner width.
- `src/styles/table.css` — 33px rows (26 compact), 30px head in mono 9.5
  uppercase, hairline separation, hover, `row-focus`, selected, zebra **off by
  default**.
- The unsourced row, per §6.
- Two new specimens on artboard 01: `table row — monograph` at the corpus
  widths, and `the unsourced row` at the indication widths. Those were the
  specimens deferred in session 14; only `reference row` (session 27) and
  `output card` (session 29) remain outstanding there.

`just check` passes: 282 pytest, 6 cargo, tsc clean.

**The unsourced row outranks everything else**

`.is-unsourced` beats zebra, hover **and** `row-focus` in the cascade, and
there is a rule for each. A row missing its source stays visibly missing it
whatever else is true of it — that is what "the single most important visual
rule in the application" has to mean in CSS.

`sourceCell()` is the only way a source cell gets built. Given empty, null or
whitespace it returns `⚠ source needed` in `secondary`. There is no path
through it that yields a blank cell.

**Three more DESIGN.md corrections — the artboards won again**

1. **The mark is 4 × 16px in the `mk` column, not a 2px row border.** §6 said
   "a 2px `secondary` marker on the leading edge", which reads as a border, and
   I built it that way first — giving a doubled mark, since §7 also reserves an
   `mk` column. Artboard 05 draws `width: 4px; height: 16px; border-radius: 1px`
   inside that column and gives the row no border at all. Corrected in both.
2. **Radius 1 exists.** That mark is radius 1, which §3's "Radius — and nothing
   else" table did not list. DESIGN.md now lists it, used for that mark and
   nothing else, and `test_design_tokens.py` expects {1, 2, 3, 4, 5}.
3. **Tables inside a record use 14px horizontal padding, not 16.** The corpus
   table is `7px 16px` as §3 says; the day log and the record's claim tables are
   `7px 14px`. Not a contradiction — a narrower column — so it is a
   `.table--inset` modifier and a new row in §3's layout table.

Each carries a `> Corrected in session 16` note in DESIGN.md.

**The mark is always in the DOM**, transparent when the row is sourced. A mark
that appears and disappears would shift every cell in the row by 4px the moment
a source is added, which is exactly the wrong feedback for adding one.

**Week 3 is complete.** Shell, tokens, components and the table primitive all
exist, and every one of them has been rendered in the actual Tauri window.

**Next session starts at:** BUILD.md §6, week 4, item **17** — artboard 02's
stat row and floor toggle: current streak · longest · floor met · minutes
worked, all in `display num`. Note that `longest_streak` has no Rust query yet
(session 03 built `current_streak` in Python only), and the floor toggle is the
`entry.floor_day` column whose meaning is still an open question from that
session.

### session 17 — artboard 02's stat row and floor toggle

**Landed**

- Rust: `TodayStats`, `today_stats()`, `set_floor_day()`, `FLOOR_MINUTES = 20`,
  and `LONGEST_RUN` — a gaps-and-islands query for `longest 96`.
- `src/screens/today.ts` + the styles. Today now opens on launch, as
  DESIGN.md §8 says it must.
- 12 Rust tests.

`just check` passes: 282 pytest, 18 cargo, tsc clean.

**The streak now exists in two languages, and a test holds them together**

§3 says the CLI does these reads directly too, so `current_streak` is in both
Python and Rust. Two implementations of one rule is exactly where drift
happens, so `src-tauri/tests/streak.rs` runs **every case from §7 test 7**
against one database and asserts the Rust answer equals the Python answer —
not equals a literal, equals *the other implementation*. If either side is
changed alone, the test fails.

`longest` is Rust-only for now; nothing in the CLI shows it yet.

**The floor is never rendered as a shortfall**

Nothing on this screen counts down, and there is no red mark or empty bar
anywhere near it. The `floor met 47 / 47` figure is a count of days that
reached the floor, not a percentage of a target.

The yes/no control's selected segment is **`ink`, not the accent** — the
artboard has it that way and it is right: this is a fact about the day, not an
action, and the accent would read as approval of one answer over the other.
The comment in `screens.css` says so.

**`floor met N / M` — M is days logged**

Artboard 02 reads `118 / 140` and does not say what the denominator is. It
could be days logged or calendar days since the first entry. Built as **days
logged**, which is the smaller reading. Open question below.

**The floor toggle opens the day.** Saying "yes, today was a floor day" on a day
with no entry creates one at 0 minutes — the same reasoning as `ledger win` in
session 05: the statement is itself a record of the day. Two tests cover it,
including one asserting that toggling twice does not open two days.

**Next session starts at:** BUILD.md §6, week 4, item **18** — the autosaving
note (2s debounce, footer `autosaved 14:22 · entry 1,412`, plus an explicit
`Save entry`) and the three deposit rows: monograph `Open` (primary), reference
`Fetch` (secondary, calls Crossref), output `Add` (quiet). The right-hand cell
of the deposit card is already reserved for it. **`Fetch` needs the sidecar,
which is session 19** — 18 should build the row and leave the call to 19.

### session 18 — the autosaving note and the three deposit rows

**Landed**

- Rust: `save_note()`, `note_for_today()`, `open_monograph()`, `add_output()`,
  and an `Error::Refused` variant so a refusal reaches the interface as a
  sentence rather than a raw SQL error.
- `src/screens/note.ts` — 2-second debounce, save on blur, explicit
  `Save entry`, footer `autosaved 13:01 · entry 47`.
- `src/screens/deposit.ts` — the three rows: monograph `Open` (primary),
  reference `Fetch` (secondary), output `Add` (quiet).
- 10 Rust tests.

`just check` passes: 282 pytest, 28 cargo, tsc clean.

**One write path, so the footer cannot lie**

The debounce, the blur and the `Save entry` button all call the same
`save_note`. A footer that says `autosaved 13:01` when a different code path
did the writing is how "it said it saved" becomes "it did not save". A failed
save writes `not saved` in the footer and the message into the trouble strip —
never silence.

Blur saves too. Two seconds of quiet is the specification; clicking away is a
stronger signal than that and waiting it out would be a way to lose a note.

**`entry 1,412` is read as the entry's id**

Artboard 02's footer is `autosaved 14:22 · entry 1,412`. That could be the
entry's row id or a length. It is rendered as the **id**: an autosave footer
saying when it saved and *which record it wrote* is the natural reading, and
the library rail labels its length figure explicitly (`62 words`) where it
means one. The artboard's own numbers do not reconcile either way — the same
screen reads `floor met 118 / 140` — so this is a fixture inconsistency, not a
clue. Open question below.

**`Fetch` is wired to a refusal, not to nothing**

Crossref is the sidecar's, and the sidecar is session 19. Pressing `Fetch`
today says so and names the CLI command that does work meanwhile. A button
that silently does nothing is worse than one that explains itself.

**The note is plain text, and the binomial in it is not italic**

Artboard 02 renders *Prunus africana* italic inside the note. That is a
`<textarea>` holding a TEXT column. Italicising it would need either rich text
— a different storage format, and not one §4 describes — or detecting binomials
in free prose, which is guessing at botany. Neither is warranted for a field
you type into. §2's "botanical names are always italic" is honoured everywhere
the *record* renders a name: the record title, table cells, output cards. Noted
as a deliberate difference.

**Two smaller differences from the artboard**

- The meta slot is **208px, not 168** — `resolves against GBIF on save`
  (artboard 08 state 6's own words) wraps at 168 and makes one row taller than
  the other two. Widening the slot was better than editing the copy.
- The output row's meta slot holds a **kind chooser**, because an output needs
  one of the five kinds and the artboard's `{{ q.meta }}` is unbound. It is the
  only invented control on the screen and it is doing real work.

**Next session starts at:** BUILD.md §6, week 4, item **19** — the fourteen-day
table, and the sidecar wired to `Fetch`. The table primitive and
`COLUMNS.dayLog` are ready; the header reads `1,025 min · 73 avg · 4 floor
days` and today's row is `row-focus`. The sidecar shim from session 12 already
runs the CLI, so `ledger ref <doi> --json` can be called through it — and its
offline failure path (session 08) is what the row's meta should show.

### session 19 — the fourteen-day table, and the sidecar actually wired to `Fetch`

**Landed**

- Rust: `day_log()` — fourteen rows always, whether or not each day was logged,
  with what was deposited on each; `parse_fetch()`; and
  `ledger_fetch_reference`, which invokes the sidecar with a **20-second
  timeout**.
- `src/screens/daylog.ts` — the table, header `596 min · 42 avg · 1 floor day`,
  today's row in `row-focus`.
- `Fetch` is live.
- 11 more Rust tests (39 in total).

`just check` passes: 282 pytest, 39 cargo, tsc clean.

**The whole architecture ran, and I have the screenshot**

The window was driven with `xdotool`: click the reference field, type
`10.1016/j.jep.2019.112202`, press return. Frontend → Rust command → 
`tauri-plugin-shell` → the capability grant → the `ledger` binary → Python →
Crossref → back as JSON → parsed → **rendered inline in `secondary` in the
row's meta slot**:

```
could not reach Crossref: <urlopen error Tunnel connection failed:
403 Forbidden> — kept as unresolved, run again later
```

That is every layer BUILD.md §3 specifies, working, including the visible
inline failure state it requires. The failure is real — Crossref is
policy-blocked in this container — which makes it a better test than a success
would have been.

**It found a bug in session 12's sidecar shim**

The shim ran `python -m ledger` without setting a working directory. The CLI
runs fine from a terminal at the repo root and fails with `No module named
ledger` from inside the app, whose cwd is `src-tauri/`. `just sidecar` now
writes a `cd` into the shim, and **always rewrites** rather than skipping when
the file exists — a stale shim fails only inside the running app, which is the
worst place to find out.

A second thing worth knowing for session 30: Tauri copies
`binaries/ledger-<triple>` to `target/debug/ledger` **at build time**. Changing
the shim is not enough; the crate has to be rebuilt.

**Deliberate details in the table**

- **A blank `min` and a `0` mean different things.** A day with no entry is
  blank; a day that was deposited against but not worked reads `0`. `day_log`
  carries a `logged` flag for exactly this, with a test.
- **Zebra is on here and nowhere else** — DESIGN.md §1 allows it "only where a
  row is very wide", and the day log is the wide table. `row-focus` had to be
  written to out-specify the zebra rule, or today's row would vanish on an even
  day.
- **`floor` is the word, in `secondary`.** No red mark, no empty bar, nothing
  counting down.
- The `floor` column carries the artboard's 12px left padding, which the table
  primitive did not support; `Column.padLeft` was added for it. Without it
  `MIN FLOOR` reads as one label.

**Next session starts at:** BUILD.md §6, week 4, item **20** — artboard 03's
corpus table. `COLUMNS.corpus` is ready and the specimen already renders at
those widths; this session is the screen, its header
(`38 monographs · 22 shown · sorted by first written`) and the footer, whose
`9 never published on` figure is the gap query `links.never_published_on()`
already proves.

### session 20 — artboard 03's corpus table

**Landed**

- Rust: `corpus()` — every record with its indication count and its **headline
  evidence**, ranked in SQL so `max` means what §4 means, plus the footer
  counts including the gap query.
- `src/evidence.ts` and `src/chips.ts` — the enum, its E-codes, its labels, the
  four-step ramp, and every chip built in one place so screens cannot disagree.
- `src/screens/corpus.ts`.
- `renderTable` grew a `footer` option; artboard 03 puts the counts **inside**
  the table card, not below it.

`just check` passes: 282 pytest, 39 cargo, tsc clean.

**The chips were wrong and the artboards said so**

`.chip` was Plex Sans 12/500. Every artboard sets status, severity and
reading-state pills in **mono, uppercase**, and the evidence chip in two parts
— a mono code and a sans label. Rebuilt to match, in two sizes, because the
artboards use two:

| | standalone (artboard 01, record header) | in a table row (artboard 03) |
|---|---|---|
| pill | mono 10 · .1em · `4px 8px` | mono 9.5 · `1px 7px` |
| evidence | gap 6 · `4px 9px` · code 10/500 · label 11.5 | gap 5 · `1px 7px` · code 9.5 · label 10.5 |

`chip--sm` is the table size. The evidence code sits beside the colour so the
exact level stays recoverable — that is the whole reason six levels can share
four steps.

**A clickable row is a `<button>`, and it kept the browser's border**

Corpus rows are the first pressable rows in the application, and they came out
with a dark bar down the right edge — the UA button border, which
`border-bottom` alone does not override. `border: 0` first, then the hairline.
Every later table with pressable rows would have inherited it.

**`New monograph` is a new modifier, matching the artboard exactly**

Artboard 03 renders it `primary` on `primary-wash` with **no ring** — the
screen's main action without a primary button's weight. `.button-quiet.is-selected`
is the nearest specified component but carries `primary-ring` and, more to the
point, is a *state*: the button is not selected. `.button-quiet--accent` is one
modifier doing one job.

**Not here yet, by plan:** the 208px filter rail (session 21) and the `find`
box (session 22). The header already reads `5 monographs · 5 shown · sorted by
first written`, so `shown` becomes meaningful the moment filters land.

**Next session starts at:** BUILD.md §6, week 4, item **21** — the filter rail:
status · family (top six, then `all 19 families`) · evidence level E1–E6 ·
flags (`never published on`, `conservation concern`, `benefit-sharing absent`).
Additive across groups, OR within a group, **all state in the URL hash**. Note
that `conservation concern` has no column in schema v4 — check that flag
against the schema before building it.

### session 21 — the filter rail, and all of its state in the URL hash

**Landed**

- `src/hash.ts` — `readHash`, `readList`, `writeList`, `toggleInList`.
- `src/screens/filters.ts` — the four groups, the facet counts, and
  `applyFilters`: **additive across groups, OR within a group**.
- The 208px rail beside the corpus, with `all 9 families` expanding the family
  group.
- Rust: `published` and `benefit_sharing` per row, so both buildable flags are
  answered from the same query the table already runs.

`just check` passes: 282 pytest, 39 cargo, tsc clean.

**The hash round trip is proven by construction**

A filter click calls `toggleInList`, which does nothing but set
`window.location.hash`. The table re-renders because `hashchange` fires and
`render()` reads the params back out. So the screenshot of `sourced` +
`E4 human uncontrolled` filtering nine records to two is a demonstration that
the state made the whole trip through the URL — there is no other path by which
that table could have changed.

Which means the back button undoes a filter and a filtered view is a place you
can return to, both for free.

**`conservation concern` cannot be built, and is rendered disabled**

The flag is in DESIGN.md §8's list, but **schema v4 records no conservation
status** — `monograph` has no such column — and §3 names only Crossref, GBIF
and WFO as enrichment sources, none of which supplies one. Deriving it from
`habitat_note` by looking for "CITES" would be inventing botanical data, which
§8 forbids in exactly those terms.

So it renders in its place in the rail, disabled, counting 0, with the reason in
its `title`. The artboard's shape is intact and the interface is not lying about
what it knows. Open question below — it needs either a column, a source, or a
decision to drop the flag.

**One header label was being truncated.** `FIRST WRITTEN` did not fit its 9.8%
column at mono 9.5 with .12em tracking. The artboard's head cells set no
overflow handling at all, so head cells now let their labels run — they are
short and fixed, and a right-aligned one runs leftward into empty space.

**A gap worth naming: the frontend has no unit tests.** `applyFilters` is a
pure function encoding a real rule, and nothing checks it but my eyes and a
screenshot. §7's four commands do not cover the frontend; I added `tsc --noEmit`
in session 12 and that is all there is. Sessions 20–29 are almost entirely
frontend. Open question below.

**Next session starts at:** BUILD.md §6, week 4, item **22** — `find` + FTS,
live hit count, footer counts. The FTS index and `ledger find` exist from
session 10; this session needs a Rust `search` command over the same `search`
table and the `find` box above the corpus table, showing `6 hits`.

### session 22 — `find` over FTS5, with the live hit count

**Landed**

- Rust: `search()` over the `search` table, `to_match()`, `nearest_name()` and
  a Levenshtein distance.
- `src/screens/find.ts` — the box above the corpus table, 120ms debounce,
  `esc` clears.
- The query joins the other filters in the hash.
- 8 Rust tests (47 in total).

`just check` passes: 282 pytest, 47 cargo, tsc clean. Verified in the running
window: typing `bark` reads `4 hits` and narrows `9 monographs · 4 shown` to the
four bark records.

**The third pair of implementations, held together the same way**

`to_match` is now in both languages, like `current_streak` and `parse_fetch`
before it. `tests/search.rs` asserts the Rust answer equals **the Python
answer** — not a literal — for ten awkward inputs including `bark"`,
`NEAR(a b)`, `a OR b`, `10.1016/j.jep` and `caïlcédrat`. Two ideas of what a
search means is the failure mode, and it fails the build now.

**A claim hit lands on its plant.** Searching a condition, a vernacular name or
a compound narrows the corpus to the records that carry it, and a plant hit
through several rows is listed once — the `hits` count reports every row, the
table shows every plant.

**The query is in the hash, but written with `replaceState`**

Filter state belongs in the URL (§8) and a search is filter state. But
assigning to `location.hash` on every keystroke would put every letter in the
back stack, turning the back button from "undo my filter" into "delete one
letter". `replaceParam` swaps the entry instead. Filters still push; only the
live query replaces.

**`nearest_name` is built but not yet shown.** It belongs to artboard 08 state
6, which is session 28. It is here because it is the same query surface and
testing it now was free.

**One clippy finding worth recording:** `Option::is_none_or` is stable since
Rust 1.82 and the crate declares `rust-version = "1.77"` — the MSRV Tauri v2
itself requires. Written out longhand rather than raising the floor, because
the floor is the portability promise and one convenience method is not worth
it.

**Week 4 is complete.** Artboards 02 and 03 are built.

**Next session starts at:** BUILD.md §6, week 5, item **23** — artboard 05, the
monograph record, which §1 says does not move and is the screen where the work
actually happens. Header, identity strip, summary strip. Note that `wfo_id` is
NULL for every record (the session 09 gap) so the identity strip will render a
blank there.

### session 23 — artboard 05: the record header, identity strip, summary strip

**Landed**

- Rust: `record(id)` — the whole header in one query, including the three
  derived figures the summary strip needs (indications, distinct references
  bound, strongest evidence) and the unsourced count from the
  `unsourced_claim` view.
- `src/screens/record.ts` and the route `#/monograph?id=N`, reached by pressing
  a corpus row.

`just check` passes: 282 pytest, 47 cargo, tsc clean. Verified in the window:

```
CORPUS › MONOGRAPH 1
Khaya senegalensis (Desr.) A.Juss.  SOURCED
Meliaceae / stem bark / African mahogany, dry-savanna belt from Senegal to Sudan
                                          wfo-id  not resolved
                                        gbif key  not resolved
                                   first written  2026-07-18
                                    last touched  2026-08-27 13:25
3 indications · 3 references bound · strongest evidence E5 RCT · 1 row unsourced
```

**The unsourced count follows into the header, as §6 requires.** `1 row
unsourced` is in `secondary` and is not softened, hidden behind a toggle, or
phrased as a suggestion.

**An identifier nobody has established reads `not resolved`, not blank**

`wfo-id` is NULL for every record — the gap raised in session 09, where no
session fills it — and `gbif key` is NULL here because GBIF is policy-blocked
in this container. Rendering those as empty space would let a missing
identifier look like a rendering bug. They say what they are.

**`Save monograph` is rendered disabled.** Nothing on the record is editable
until sessions 24–27, so there is nothing to save. Same reasoning as `Fetch`
before session 19 and the `conservation concern` flag: a control that silently
does nothing is worse than one that says why it is off.

**The authority is Fraunces 16 upright**, not Plex Sans — artboard 05 sets it
that way, and it is the same rule as everywhere else: the binomial is italic,
the authority never is.

**Next session starts at:** BUILD.md §6, week 5, item **24** — the vernacular
and indication sections with inline add. Each section has a count, a `+ add`
quiet button, and per-row sourcing; the indications table already has its
column widths in `COLUMNS.indications` and its unsourced row proven in session
16.

### session 24 — the vernacular and indication sections, with inline add

**Landed**

- Rust: `claims()`, `add_claim()`, `claim_columns()` — the column mapping that
  is the twin of `ledger.claims.CLAIM_TABLES`, with a test asserting the two
  agree.
- `src/screens/section.ts` — one section component: heading with a count and
  its unsourced part, `+ add`, the table, and the inline add row. Every claim
  section on artboard 05 has this shape, so it is built once.
- `COLUMNS.vernacular` — artboard 05 gives this table in pixels rather than in
  DESIGN.md §7, converted to percentages of the record column.
- 9 Rust tests (56 in total).

`just check` passes: 282 pytest, 56 cargo, tsc clean.

**§6 propagates the whole way, and the screenshots show it**

`1 unsourced` appears in the section heading in `secondary`, the row is tinted
with its 4 × 16 mark, the source cell reads `⚠ source needed`, and the record
header reads `2 rows unsourced`. One rule, four places, one definition —
everything reads the `unsourced_claim` view.

**Two real bugs, both found by driving the window**

1. **The inline add offered a blank evidence level.** A Rust test caught it
   first: `evidence` is one of six named values and the CHECK refuses an empty
   string, so the add row would have failed on submit. Enum columns now get a
   **chooser** rather than a field — the record cannot offer to write something
   the database will refuse.
2. **`focus()` was called on a detached element.** `addRow` focused its first
   field while the row was still being built, before it was in the document, so
   it did nothing: typing went to whatever had focus before, and `enter` pressed
   a **nav button**. Fixed by focusing after insertion. No test would have found
   this; only typing into the real window did.

Verified end to end: `+ add name` → typed `gedu nooma / Wolof / Senegal / field
notes 2026-08` → `enter` → written to SQLite, and the heading went `3` to `4`.

**A source that is a reference reads `R2` in `primary`**, and free text reads
plain. Both come from the one place a source cell is built.

**Next session starts at:** BUILD.md §6, week 5, item **25** — the constituent
and safety sections with severity chips. `renderSection` already takes them;
this session is two more `SectionSpec`s, the `severity` chooser, and
`claim_columns` already names their columns.

### session 25 — the constituent and safety sections, with severity chips

**Landed**

- `COLUMNS.constituent` and `COLUMNS.safety`, converted from artboard 05's
  pixel widths and normalised.
- Two more `SectionSpec`s. `renderSection` took them without changing.
- `SEVERITY` in `evidence.ts`, and the safety section's severity **chooser** —
  the same reasoning as `evidence` in session 24: three named values, and a
  blank is not one of them.

`just check` passes: 282 pytest, 56 cargo, tsc clean.

**The section component paid for itself.** Two sections, no new component code:
a spec each, one `cell` override for the severity chip, one `meta` for
`1 critical`. That is what "three, then abstract" was waiting for — vernacular
and indications were two, and these are three and four.

**The InChIKey is monospace**, as §2 requires: every date, DOI, InChIKey,
minute count and percentage. It is a column flag on the primitive, not a
per-screen decision.

**The safety heading names criticals, not counts of everything.** `3 · 1
unsourced` when a row is unsourced, `3 · 1 critical` when one is critical, and
just the count when neither. A safety section that buried a critical finding
under a class list would be the wrong emphasis.

**Next session starts at:** BUILD.md §6, week 5, item **26** — the prose
sections: summary (74ch, `sources R1, R2, R6`, `rewritten <date>`), preparation
(prose plus a field-note reference), and benefit-sharing (`agreement on file ·
MTA-2025-014 · expires 2028-06`). Benefit-sharing is **not optional chrome**:
it appears on every monograph, and its absence is already a corpus filter flag.

### session 26 — the prose sections: summary, preparation, benefit-sharing

**Landed**

- Rust: `benefit_sharing()`, `save_benefit_sharing()`, `save_prose()`,
  `section_sources()`.
- `src/screens/prose.ts` — prose at 74ch, `sources R2, R3` in `primary`,
  `rewritten 2026-08-27`, and in-place editing.
- Benefit-sharing with its narrative, `agreement on file · MTA-2025-014 ·
  expires 2028-06`.

`just check` passes: 282 pytest, 56 cargo, tsc clean.

**Rewriting the summary stamps its date; writing the same text again does not.**
That rule already existed on the Python side (session 04) and now exists on the
Rust side, for the same reason: `rewritten 2026-08-27` has to mean the day the
words changed, or it is decoration.

**Benefit-sharing appears whether or not there is one**

It is not optional chrome — §8 says so, and its absence is already a corpus
filter flag. A record with no agreement gets the section anyway, reading *"No
consent, attribution or agreement is recorded for this record"* with
`no agreement recorded` in `secondary` beside the heading and a
`+ record consent` button. Leaving the section off when it is empty would make
the gap invisible, which is exactly backwards for the one thing on this screen
that governs a real obligation.

**`Save monograph` is disabled, and this is a design question for you**

Artboard 05 puts it in the header strip, which implies a form: edit, then
commit. But every edit on this screen writes through the moment it is made — an
added claim row on `enter`, a prose section on `save`. So there is never
anything pending for a global save to commit.

It stays in its place with the reason in its title
(*"every change on this record is written as you make it"*) rather than being a
button that does nothing. If you want deferred save semantics instead — edit
freely, commit or discard — that is a real and defensible design, and it is a
change to how the whole record behaves, not a button. Open question below.

**Next session starts at:** BUILD.md §6, week 5, item **27** — the references
section (`R1`–`Rn`, citation, DOI, read state), the 224px sticky rail (section
jump list with counts, unsourced counts in `secondary`, `cited by your
outputs`, `3 references queued, unread →`), and the reviewed-status block at
the foot of the record. That block is DESIGN.md §6's closing line and the
database already enforces what it says.

### session 27 — the references section, the sticky rail, the reviewed block

**Landed**

- Rust: `record_references()`, `cited_by_outputs()`, `queued_reading()`,
  `unsourced_by_section()`.
- `src/screens/references.ts` — `R1`–`Rn`, citation, DOI, reading state, and
  which sections cite each one.
- `src/screens/rail.ts` — the 224px rail, sticky at top 0: the jump list with
  counts and unsourced counts in `secondary`, `cited by your outputs`, and
  `references queued, unread →`.
- `renderReviewedStatus` — DESIGN.md §6's closing line, at the foot of the
  record.
- 3 more Rust tests (59 in total).

`just check` passes: 282 pytest, 59 cargo, tsc clean.

**Week 5 is complete. The monograph record is built** — the screen §1 says does
not move, and the one it says the product actually is.

**`R…` is a position in the record, not a library id**

Artboard 05 labels the section `R1`–`Rn` and the summary cites `sources R1, R2,
R6`. I had first rendered the library's row id, which happened to look
plausible on a small database, would have read `R187` on a real one and — worse
— would not have matched the numbers in the references section directly below.
Every `R…` on the screen now comes from one map built from the record's own
bound list.

One consequence worth having: a `source_note` that reads `R5` — free text
someone typed — renders plain, while a real binding renders in `primary`. The
screen distinguishes a citation from a string that looks like one.

**Two bugs the screenshots found**

1. **`6 references queued` on a record with three.** The join to
   `monograph_reference` duplicates a reference cited in two sections.
   `count(DISTINCT r.id)`, with a test that binds one reference twice and
   asserts both the references list and the queued count read 1.
2. The rail's `cited by your outputs` had to say something when empty. It reads
   **`never published on`** — the corpus footer's gap query seen from the other
   end, and not softened.

**Next session starts at:** BUILD.md §6, week 6, item **28** — artboard 08
states 1, 2, 4, 5, 6, skipping 3 (overload, v0.2). Built as **real renders, not
mocks**: first run at 0 rows, one record at n = 1, the unresolved-name queue,
the broken streak, and no results. `nearest_name` has been waiting since
session 22 for state 6.

### session 28 — artboard 08's states, as real renders

**Landed**

- Rust: `broken_streak()`, `queue_position()`, `next_skeleton()`,
  `set_name_by_hand()`, `parse_resolution()`, and a `ledger_resolve_name`
  sidecar command.
- `src/screens/states.ts` — states **1, 2, 4, 5, 6**. State 3 (overload) is
  v0.2 and is not here.
- 3 more Rust tests (62 in total).

`just check` passes: 282 pytest, 62 cargo, tsc clean.

**They are renders, not mocks.** Each state is what its screen does when the
database is in that shape, and each was screenshotted against a database
actually in it:

| state | how it was produced |
|---|---|
| 1 · first run | a freshly migrated, empty ledger |
| 2 · one record | a ledger with exactly one monograph and one indication |
| 4 · unresolved name | the demo record, whose `gbif_key` is genuinely NULL |
| 5 · broken streak | a 41-day run ending four days ago |
| 6 · no results | `Sutherlandia frutescens` typed into the real find box |

State 5 came out reading *"The 41-day streak ended on 2026-08-23. 4 days
without an entry."* with the four days listed, `Log a floor day — 20 min`,
`Open next skeleton`, `counting resumes at 1`, and `longest 41` still in the
stat row above. **No flame, no "don't break the chain", no offer to restore
it** — §8's guardrail, kept.

State 6 reads *"No monograph, no reference, no output mentions this name."*,
`searched 9 monographs · 4 references · 1 output · 0 ms`, `nearest in corpus:
Vernonia amygdalina · edit distance 16`, and `New — Sutherlandia frutescens`
with `resolves against GBIF on save`. `nearest_name` had been waiting since
session 22.

**State 4 is the whole of state 4, not a sketch**

It lists GBIF's candidates with their keys and scores and offers all three
actions the artboard names: `Accept top match`, `Enter name by hand`,
`Keep in queue`. Accepting calls the sidecar with `--accept`; entering by hand
writes only `accepted_name` and leaves the identifiers NULL, so the record
stays in the queue until something confirms it.

The candidate list needs GBIF, which is policy-blocked here, so it is the one
part of the five states without a screenshot. It has three tests against the
**actual JSON `ledger/commands/resolve.py` prints** — including the
below-threshold shape with two candidates.

**`N` opens a skeleton, because state 1 promises it does.** It is ignored while
an input, textarea or select has focus: a field owns its own keystrokes.

**Next session starts at:** BUILD.md §6, week 6, item **29** — The Wall.
`27 outputs · 2024-01-02 → 2026-06-18 · newest first`, kind counts across the
top, grouped by year newest-first. Outputs with no plant read `whole corpus` or
`method, no plant` — upright and muted, never italic. **No pagination, no
load-more: the length of the scroll is the point.**

### session 29 — The Wall

**Landed**

- Rust: `wall()` — every output newest first with the plants it was about, the
  span, and the counts by kind including the zeroes.
- `src/screens/wall.ts`.

`just check` passes: 282 pytest, 62 cargo, tsc clean. Verified in the window:
`The Wall · 4 outputs · 2024-11-19 → 2026-08-27 · newest first`, kind counts
across the top each in its own colour, grouped by year newest-first.

**No pagination, no load-more.** The length of the scroll is the point, and
there is no code here that could grow into either.

**A plantless output reads `whole corpus`, upright and muted.** Never italic —
it is not a name, and the rule that botanical names are italic only means
anything if things that are not names are not.

**One thing the schema cannot answer**

Artboard 04 gives two phrasings for an output about no particular plant:
`whole corpus` **and** `method, no plant`. Schema v4 has no column that
distinguishes them — an output either has `output_monograph` rows or it does
not. `whole corpus` is used for both, as the more general of the author's own
two phrases. Open question below.

**Next session starts at:** BUILD.md §6, week 6, item **30** — the ship: the
PyInstaller freeze, `cargo tauri build`, launching from `/Applications` on a
machine with no Python, `README.md`, tag `v0.1`. **Two of those cannot be done
here** — this is Linux, and there is no Mac to launch from `/Applications` on.
Expect to land the freeze scripting and the README, and to hand you a
documented list of what must be run on the Mac.

---

## Open questions

Carried from BUILD.md §8, plus what sessions have added. Raise these; do not
answer them alone.

- ~~Vanilla DOM vs Preact~~ — **decided session 12: vanilla DOM.** Reasoning in
  that entry. Revisit only if session 24's inline editing turns messy.
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

- **New (04):** does the artboard 08 state 4 candidate list need to persist, or
  can it be fetched live at review time? Built as live. If it must persist there
  is no spare migration in schema v4 — decide in session 09.

- **New (06, settled in 11 — needs your confirmation):** §4's git habit is
  `sqlite3 ledger.sqlite .dump`. That ordering cannot restore this schema and
  has no answer for FTS5's shadow tables. `just dump` now calls `ledger dump`,
  and restoring wants `ledger restore` so the index is rebuilt. Amend §4 or
  tell me to find another way.

- **New (08):** where does `reference.access` come from? Crossref does not say
  reliably. Left NULL rather than guessed. Unpaywall would answer it but is
  another network dependency and another key.
- **New (08):** the Crossref fixture is a shape fixture, not a recording,
  because this environment is policy-blocked from `api.crossref.org`. Replace it
  before v0.1 — `ledger/tests/fixtures/README.md` has the command.

- **New (09):** *(raised, needs a decision)* no session in §6 resolves
  `monograph.wfo_id`, but §3 names WFO and invariant 2 requires the ID. It will
  be NULL for every record in v0.1 and artboard 05's identity strip will show a
  blank. Allocate a session, or decide to ship without it.

- **New (17):** in `floor met 118 / 140`, is 140 days *logged* or calendar days
  since the first entry? Built as days logged.

- **New (18):** is `entry 1,412` in artboard 02's autosave footer the entry's
  row id, or a length? Rendered as the id.

- **New (21):** `conservation concern` is a corpus filter flag in DESIGN.md §8,
  but schema v4 has no conservation column and §3 names no source for one.
  Rendered disabled. It needs a column, an enrichment source, or dropping.
- **New (21):** should the frontend get a test runner? `applyFilters`, the hash
  helpers and the evidence ramp are pure functions encoding real rules, and
  nothing checks them. Adding `vitest` is a dependency and a sixth command in
  `just check`; §7 asks for neither. Not added.

- **New (26):** artboard 05's `Save monograph` implies a form — edit, then
  commit — but every edit on the record writes through immediately, so there is
  nothing pending for it to save. It is rendered disabled with that reason.
  Deferred save is a defensible alternative; it changes how the whole record
  behaves, so it is yours to choose.

- **New (29):** artboard 04 gives two phrasings for an output about no
  particular plant — `whole corpus` and `method, no plant` — but schema v4
  cannot tell them apart. `whole corpus` is used for both. Needs a column or a
  single phrase.

---

## Plan health

The §1 scope reckoning still holds as written: v0.1 is five screens, light
theme only, monograph does not move.

One gap in §6 itself, found in session 09: **no session resolves `wfo_id`**,
though §3 names WFO as an enrichment source and invariant 2 requires the
identifier. Everything else in weeks 1–2 has landed where the plan said it
would.
