-- 000_init.sql — the four tables the graph hangs off.
-- Applied by `ledger migrate`; stamps PRAGMA user_version = 1.
--
-- A daily entry points at the work deposited that day; monographs carry the
-- botanical record; references are what the claims cite; outputs are what was
-- published. Claim rows and link tables arrive in 001 and 002.

-- One row per day worked. `date` is the natural key — a day is logged once.
CREATE TABLE entry (
    id          INTEGER PRIMARY KEY,
    date        TEXT    NOT NULL UNIQUE,          -- ISO 8601, YYYY-MM-DD
    minutes     INTEGER NOT NULL DEFAULT 0 CHECK (minutes >= 0),
    note        TEXT    NOT NULL DEFAULT '',
    -- The floor is 20 minutes and a floor day is a success, never a shortfall.
    floor_day   INTEGER NOT NULL DEFAULT 0 CHECK (floor_day IN (0, 1)),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- The botanical record. accepted_name stays NULL until a name resolves above
-- the GBIF confidence threshold; an unresolved record stays 'skeleton' and
-- waits in the review queue. Names change, identifiers do not — hence wfo_id.
CREATE TABLE monograph (
    id                    INTEGER PRIMARY KEY,
    accepted_name         TEXT,
    authority             TEXT,
    family                TEXT,
    part                  TEXT,
    habitat_note          TEXT,
    wfo_id                TEXT,
    gbif_key              INTEGER,
    gbif_confidence       REAL,
    status                TEXT NOT NULL DEFAULT 'skeleton'
                          CHECK (status IN ('skeleton', 'drafted', 'sourced', 'reviewed')),
    summary               TEXT,
    summary_rewritten_at  TEXT,
    preparation           TEXT,
    first_written         TEXT NOT NULL DEFAULT (date('now')),
    last_touched          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The library. A reference carries a DOI or an ISBN; why_it_mattered is the
-- reason to keep a library rather than a folder of PDFs.
CREATE TABLE reference (
    id               INTEGER PRIMARY KEY,
    doi              TEXT UNIQUE,
    isbn             TEXT UNIQUE,
    title            TEXT NOT NULL,
    authors          TEXT,
    journal          TEXT,
    volume           TEXT,
    year             INTEGER,
    type             TEXT,
    access           TEXT,
    read_state       TEXT    NOT NULL DEFAULT 'queued'
                     CHECK (read_state IN ('queued', 'reading', 'read')),
    added_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    added_from       TEXT,
    opened_count     INTEGER NOT NULL DEFAULT 0 CHECK (opened_count >= 0),
    why_it_mattered  TEXT,
    why_edited_at    TEXT
);

-- What was published. Linked to the entry it was deposited against.
CREATE TABLE output (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL
                CHECK (kind IN ('paper', 'talk', 'long-form', 'release', 'note')),
    title       TEXT NOT NULL,
    venue       TEXT,
    date        TEXT NOT NULL,                     -- ISO 8601, YYYY-MM-DD
    url         TEXT,
    entry_id    INTEGER REFERENCES entry(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
