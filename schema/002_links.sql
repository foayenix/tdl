-- 002_links.sql — the edges of the graph, and the phone inbox.
-- Applied by `ledger migrate`; stamps PRAGMA user_version = 3.
--
-- The connectedness is the whole value (BUILD.md §2). These four tables are
-- what let the corpus answer "which plants have I written about that have no
-- human-trial evidence and that I have never published on?" in one query.

-- A reference bound to a record, and where in the record it is cited.
-- The library's detail rail reads this back the other way: "cited by
-- monographs — which records use it and in which section".
CREATE TABLE monograph_reference (
    id            INTEGER PRIMARY KEY,
    monograph_id  INTEGER NOT NULL REFERENCES monograph(id) ON DELETE CASCADE,
    reference_id  INTEGER NOT NULL REFERENCES reference(id) ON DELETE CASCADE,
    section       TEXT CHECK (section IN ('summary', 'vernacular', 'indication',
                                          'constituent', 'safety', 'preparation',
                                          'benefit_sharing')),
    bound_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (monograph_id, reference_id, section)
);

-- Which plants an output was about. An output with no rows here is the
-- `whole corpus` / `method, no plant` case The Wall renders upright and muted.
CREATE TABLE output_monograph (
    id            INTEGER PRIMARY KEY,
    output_id     INTEGER NOT NULL REFERENCES output(id) ON DELETE CASCADE,
    monograph_id  INTEGER NOT NULL REFERENCES monograph(id) ON DELETE CASCADE,
    UNIQUE (output_id, monograph_id)
);

CREATE TABLE reference_tag (
    id            INTEGER PRIMARY KEY,
    reference_id  INTEGER NOT NULL REFERENCES reference(id) ON DELETE CASCADE,
    tag           TEXT    NOT NULL,
    UNIQUE (reference_id, tag)
);

-- One row per line appended by the phone shortcut. Lines that cannot be
-- classified keep kind NULL and stay pending for the review overlay; the nav
-- badge counts exactly those rows that are not yet consumed.
CREATE TABLE inbox_line (
    id           INTEGER PRIMARY KEY,
    captured_at  TEXT,                              -- the line's own timestamp
    raw          TEXT    NOT NULL,
    kind         TEXT,                              -- mono | ref | win | note, NULL = unclassified
    body         TEXT,
    destination  TEXT,
    consumed_at  TEXT,
    added_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (captured_at, raw)
);
