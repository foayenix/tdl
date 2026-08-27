# STATE.md — The Deposit Ledger

Where the build actually is. Updated at the end of every session (BUILD.md §0).

**Release target:** v0.1 — five screens, light theme only, by 5 Oct.
**Now:** week 2, the corpus in the database — item 11 next.

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

- **New (04):** does the artboard 08 state 4 candidate list need to persist, or
  can it be fetched live at review time? Built as live. If it must persist there
  is no spare migration in schema v4 — decide in session 09.

- **New (06):** §4's git habit is `sqlite3 ledger.sqlite .dump`. That ordering
  cannot restore this schema (see session 06) and the binary is not present
  here. `just dump` is planned to shell into `ledger dump` instead — confirm.

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

---

## Plan health

The §1 scope reckoning still holds as written: v0.1 is five screens, light
theme only, monograph does not move.

One gap in §6 itself, found in session 09: **no session resolves `wfo_id`**,
though §3 names WFO as an enrichment source and invariant 2 requires the
identifier. Everything else in weeks 1–2 has landed where the plan said it
would.
