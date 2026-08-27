-- 001_claims.sql — the claim rows, and the invariant that guards `reviewed`.
-- Applied by `ledger migrate`; stamps PRAGMA user_version = 2.
--
-- Every claim row carries a source: a reference_id, or free text for a field
-- record (BUILD.md §4). Both NULL or blank means unsourced, and an unsourced
-- row is the single most important visual rule in the application — it tints
-- its row, it counts in its section header, and it holds the record back from
-- `reviewed`. That last part is a hard invariant and lives here, not in the UI.

CREATE TABLE vernacular (
    id                   INTEGER PRIMARY KEY,
    monograph_id         INTEGER NOT NULL REFERENCES monograph(id) ON DELETE CASCADE,
    name                 TEXT    NOT NULL,
    language             TEXT,
    region               TEXT,
    source_reference_id  INTEGER REFERENCES reference(id) ON DELETE SET NULL,
    source_note          TEXT,
    added_at             TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- A claim is who used it for what, where — not just a condition string.
CREATE TABLE indication (
    id                   INTEGER PRIMARY KEY,
    monograph_id         INTEGER NOT NULL REFERENCES monograph(id) ON DELETE CASCADE,
    condition            TEXT    NOT NULL,
    tradition            TEXT,
    region               TEXT,
    evidence             TEXT    NOT NULL DEFAULT 'traditional_only'
                         CHECK (evidence IN ('traditional_only', 'in_vitro', 'in_vivo',
                                             'human_uncontrolled', 'rct', 'meta_analysis')),
    source_reference_id  INTEGER REFERENCES reference(id) ON DELETE SET NULL,
    source_note          TEXT,
    added_at             TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE constituent (
    id                   INTEGER PRIMARY KEY,
    monograph_id         INTEGER NOT NULL REFERENCES monograph(id) ON DELETE CASCADE,
    compound             TEXT    NOT NULL,
    class                TEXT,
    inchikey             TEXT,
    source_reference_id  INTEGER REFERENCES reference(id) ON DELETE SET NULL,
    source_note          TEXT,
    added_at             TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE safety (
    id                   INTEGER PRIMARY KEY,
    monograph_id         INTEGER NOT NULL REFERENCES monograph(id) ON DELETE CASCADE,
    kind                 TEXT    NOT NULL,
    finding              TEXT    NOT NULL,
    severity             TEXT    NOT NULL DEFAULT 'note'
                         CHECK (severity IN ('critical', 'caution', 'note')),
    source_reference_id  INTEGER REFERENCES reference(id) ON DELETE SET NULL,
    source_note          TEXT,
    added_at             TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- One row per monograph. Not optional chrome: it records consent, named
-- attribution and the agreement under which the knowledge was collected.
CREATE TABLE benefit_sharing (
    id                   INTEGER PRIMARY KEY,
    monograph_id         INTEGER NOT NULL UNIQUE REFERENCES monograph(id) ON DELETE CASCADE,
    narrative            TEXT,
    agreement_ref        TEXT,
    expires              TEXT,
    consent_recorded_at  TEXT
);

-- Every unsourced claim row in the database, with the record it holds back.
-- The triggers below read this, and so does every count the UI shows.
CREATE VIEW unsourced_claim AS
    SELECT 'vernacular'  AS claim_table, id AS claim_id, monograph_id FROM vernacular
     WHERE source_reference_id IS NULL AND coalesce(trim(source_note), '') = ''
    UNION ALL
    SELECT 'indication',  id, monograph_id FROM indication
     WHERE source_reference_id IS NULL AND coalesce(trim(source_note), '') = ''
    UNION ALL
    SELECT 'constituent', id, monograph_id FROM constituent
     WHERE source_reference_id IS NULL AND coalesce(trim(source_note), '') = ''
    UNION ALL
    SELECT 'safety',      id, monograph_id FROM safety
     WHERE source_reference_id IS NULL AND coalesce(trim(source_note), '') = '';

-- Invariant 1, first direction: a record cannot advance to `reviewed` while it
-- holds an unsourced claim row.
CREATE TRIGGER monograph_reviewed_requires_sources
BEFORE UPDATE OF status ON monograph
WHEN NEW.status = 'reviewed' AND OLD.status <> 'reviewed'
BEGIN
    SELECT RAISE(ABORT, 'unsourced claim rows: status cannot advance to reviewed')
    WHERE EXISTS (SELECT 1 FROM unsourced_claim WHERE monograph_id = NEW.id);
END;

CREATE TRIGGER monograph_inserted_reviewed_requires_sources
BEFORE INSERT ON monograph
WHEN NEW.status = 'reviewed'
BEGIN
    SELECT RAISE(ABORT, 'unsourced claim rows: status cannot advance to reviewed')
    WHERE EXISTS (SELECT 1 FROM unsourced_claim WHERE monograph_id = NEW.id);
END;

-- Invariant 1, second direction: an unsourced row cannot appear on — or be
-- un-sourced within — a record that is already `reviewed`. Without these the
-- invariant is only a doorway, not a wall.
CREATE TRIGGER vernacular_insert_requires_source_when_reviewed
BEFORE INSERT ON vernacular
WHEN NEW.source_reference_id IS NULL AND coalesce(trim(NEW.source_note), '') = ''
BEGIN
    SELECT RAISE(ABORT, 'a reviewed monograph cannot take an unsourced row')
    WHERE (SELECT status FROM monograph WHERE id = NEW.monograph_id) = 'reviewed';
END;

CREATE TRIGGER vernacular_update_requires_source_when_reviewed
BEFORE UPDATE ON vernacular
WHEN NEW.source_reference_id IS NULL AND coalesce(trim(NEW.source_note), '') = ''
BEGIN
    SELECT RAISE(ABORT, 'a reviewed monograph cannot take an unsourced row')
    WHERE (SELECT status FROM monograph WHERE id = NEW.monograph_id) = 'reviewed';
END;

CREATE TRIGGER indication_insert_requires_source_when_reviewed
BEFORE INSERT ON indication
WHEN NEW.source_reference_id IS NULL AND coalesce(trim(NEW.source_note), '') = ''
BEGIN
    SELECT RAISE(ABORT, 'a reviewed monograph cannot take an unsourced row')
    WHERE (SELECT status FROM monograph WHERE id = NEW.monograph_id) = 'reviewed';
END;

CREATE TRIGGER indication_update_requires_source_when_reviewed
BEFORE UPDATE ON indication
WHEN NEW.source_reference_id IS NULL AND coalesce(trim(NEW.source_note), '') = ''
BEGIN
    SELECT RAISE(ABORT, 'a reviewed monograph cannot take an unsourced row')
    WHERE (SELECT status FROM monograph WHERE id = NEW.monograph_id) = 'reviewed';
END;

CREATE TRIGGER constituent_insert_requires_source_when_reviewed
BEFORE INSERT ON constituent
WHEN NEW.source_reference_id IS NULL AND coalesce(trim(NEW.source_note), '') = ''
BEGIN
    SELECT RAISE(ABORT, 'a reviewed monograph cannot take an unsourced row')
    WHERE (SELECT status FROM monograph WHERE id = NEW.monograph_id) = 'reviewed';
END;

CREATE TRIGGER constituent_update_requires_source_when_reviewed
BEFORE UPDATE ON constituent
WHEN NEW.source_reference_id IS NULL AND coalesce(trim(NEW.source_note), '') = ''
BEGIN
    SELECT RAISE(ABORT, 'a reviewed monograph cannot take an unsourced row')
    WHERE (SELECT status FROM monograph WHERE id = NEW.monograph_id) = 'reviewed';
END;

CREATE TRIGGER safety_insert_requires_source_when_reviewed
BEFORE INSERT ON safety
WHEN NEW.source_reference_id IS NULL AND coalesce(trim(NEW.source_note), '') = ''
BEGIN
    SELECT RAISE(ABORT, 'a reviewed monograph cannot take an unsourced row')
    WHERE (SELECT status FROM monograph WHERE id = NEW.monograph_id) = 'reviewed';
END;

CREATE TRIGGER safety_update_requires_source_when_reviewed
BEFORE UPDATE ON safety
WHEN NEW.source_reference_id IS NULL AND coalesce(trim(NEW.source_note), '') = ''
BEGIN
    SELECT RAISE(ABORT, 'a reviewed monograph cannot take an unsourced row')
    WHERE (SELECT status FROM monograph WHERE id = NEW.monograph_id) = 'reviewed';
END;
