-- 003_fts.sql — full-text search, and the triggers that keep it honest.
-- Applied by `ledger migrate`; stamps PRAGMA user_version = 4 — schema v4,
-- which is the version artboard 08's footer shows.
--
-- One index over everything `find` searches. Claim rows are indexed as
-- themselves and carry their monograph_id, so searching a condition, a
-- vernacular name or a compound lands on the plant without the monograph row
-- having to be rebuilt every time a claim changes.
--
-- Triggers fire on insert, update AND delete. The delete half is the one that
-- rots quietly if it is missing: a search that returns records you deleted is
-- worse than no search.

CREATE VIRTUAL TABLE search USING fts5(
    kind UNINDEXED,
    row_id UNINDEXED,
    monograph_id UNINDEXED,
    title,
    body,
    tokenize = 'unicode61 remove_diacritics 2'
);

-- monograph
CREATE TRIGGER search_monograph_insert AFTER INSERT ON "monograph" BEGIN
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('monograph', NEW.id, NEW.id, coalesce(NEW.accepted_name, ''),
            trim(coalesce(NEW."authority", '') || ' ' || coalesce(NEW."family", '') || ' ' || coalesce(NEW."part", '') || ' ' || coalesce(NEW."habitat_note", '') || ' ' || coalesce(NEW."summary", '') || ' ' || coalesce(NEW."preparation", '')));
END;

CREATE TRIGGER search_monograph_update AFTER UPDATE ON "monograph" BEGIN
    DELETE FROM search WHERE kind = 'monograph' AND row_id = OLD.id;
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('monograph', NEW.id, NEW.id, coalesce(NEW.accepted_name, ''),
            trim(coalesce(NEW."authority", '') || ' ' || coalesce(NEW."family", '') || ' ' || coalesce(NEW."part", '') || ' ' || coalesce(NEW."habitat_note", '') || ' ' || coalesce(NEW."summary", '') || ' ' || coalesce(NEW."preparation", '')));
END;

CREATE TRIGGER search_monograph_delete AFTER DELETE ON "monograph" BEGIN
    DELETE FROM search WHERE kind = 'monograph' AND row_id = OLD.id;
END;

-- reference
CREATE TRIGGER search_reference_insert AFTER INSERT ON "reference" BEGIN
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('reference', NEW.id, NULL, coalesce(NEW.title, ''),
            trim(coalesce(NEW."authors", '') || ' ' || coalesce(NEW."journal", '') || ' ' || coalesce(NEW."doi", '') || ' ' || coalesce(NEW."isbn", '') || ' ' || coalesce(NEW."why_it_mattered", '')));
END;

CREATE TRIGGER search_reference_update AFTER UPDATE ON "reference" BEGIN
    DELETE FROM search WHERE kind = 'reference' AND row_id = OLD.id;
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('reference', NEW.id, NULL, coalesce(NEW.title, ''),
            trim(coalesce(NEW."authors", '') || ' ' || coalesce(NEW."journal", '') || ' ' || coalesce(NEW."doi", '') || ' ' || coalesce(NEW."isbn", '') || ' ' || coalesce(NEW."why_it_mattered", '')));
END;

CREATE TRIGGER search_reference_delete AFTER DELETE ON "reference" BEGIN
    DELETE FROM search WHERE kind = 'reference' AND row_id = OLD.id;
END;

-- output
CREATE TRIGGER search_output_insert AFTER INSERT ON "output" BEGIN
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('output', NEW.id, NULL, coalesce(NEW.title, ''),
            trim(coalesce(NEW."kind", '') || ' ' || coalesce(NEW."venue", '') || ' ' || coalesce(NEW."url", '')));
END;

CREATE TRIGGER search_output_update AFTER UPDATE ON "output" BEGIN
    DELETE FROM search WHERE kind = 'output' AND row_id = OLD.id;
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('output', NEW.id, NULL, coalesce(NEW.title, ''),
            trim(coalesce(NEW."kind", '') || ' ' || coalesce(NEW."venue", '') || ' ' || coalesce(NEW."url", '')));
END;

CREATE TRIGGER search_output_delete AFTER DELETE ON "output" BEGIN
    DELETE FROM search WHERE kind = 'output' AND row_id = OLD.id;
END;

-- vernacular
CREATE TRIGGER search_vernacular_insert AFTER INSERT ON "vernacular" BEGIN
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('vernacular', NEW.id, NEW.monograph_id, coalesce(NEW.name, ''),
            trim(coalesce(NEW."language", '') || ' ' || coalesce(NEW."region", '') || ' ' || coalesce(NEW."source_note", '')));
END;

CREATE TRIGGER search_vernacular_update AFTER UPDATE ON "vernacular" BEGIN
    DELETE FROM search WHERE kind = 'vernacular' AND row_id = OLD.id;
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('vernacular', NEW.id, NEW.monograph_id, coalesce(NEW.name, ''),
            trim(coalesce(NEW."language", '') || ' ' || coalesce(NEW."region", '') || ' ' || coalesce(NEW."source_note", '')));
END;

CREATE TRIGGER search_vernacular_delete AFTER DELETE ON "vernacular" BEGIN
    DELETE FROM search WHERE kind = 'vernacular' AND row_id = OLD.id;
END;

-- indication
CREATE TRIGGER search_indication_insert AFTER INSERT ON "indication" BEGIN
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('indication', NEW.id, NEW.monograph_id, coalesce(NEW.condition, ''),
            trim(coalesce(NEW."tradition", '') || ' ' || coalesce(NEW."region", '') || ' ' || coalesce(NEW."evidence", '') || ' ' || coalesce(NEW."source_note", '')));
END;

CREATE TRIGGER search_indication_update AFTER UPDATE ON "indication" BEGIN
    DELETE FROM search WHERE kind = 'indication' AND row_id = OLD.id;
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('indication', NEW.id, NEW.monograph_id, coalesce(NEW.condition, ''),
            trim(coalesce(NEW."tradition", '') || ' ' || coalesce(NEW."region", '') || ' ' || coalesce(NEW."evidence", '') || ' ' || coalesce(NEW."source_note", '')));
END;

CREATE TRIGGER search_indication_delete AFTER DELETE ON "indication" BEGIN
    DELETE FROM search WHERE kind = 'indication' AND row_id = OLD.id;
END;

-- constituent
CREATE TRIGGER search_constituent_insert AFTER INSERT ON "constituent" BEGIN
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('constituent', NEW.id, NEW.monograph_id, coalesce(NEW.compound, ''),
            trim(coalesce(NEW."class", '') || ' ' || coalesce(NEW."inchikey", '') || ' ' || coalesce(NEW."source_note", '')));
END;

CREATE TRIGGER search_constituent_update AFTER UPDATE ON "constituent" BEGIN
    DELETE FROM search WHERE kind = 'constituent' AND row_id = OLD.id;
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('constituent', NEW.id, NEW.monograph_id, coalesce(NEW.compound, ''),
            trim(coalesce(NEW."class", '') || ' ' || coalesce(NEW."inchikey", '') || ' ' || coalesce(NEW."source_note", '')));
END;

CREATE TRIGGER search_constituent_delete AFTER DELETE ON "constituent" BEGIN
    DELETE FROM search WHERE kind = 'constituent' AND row_id = OLD.id;
END;

-- safety
CREATE TRIGGER search_safety_insert AFTER INSERT ON "safety" BEGIN
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('safety', NEW.id, NEW.monograph_id, coalesce(NEW.finding, ''),
            trim(coalesce(NEW."kind", '') || ' ' || coalesce(NEW."severity", '') || ' ' || coalesce(NEW."source_note", '')));
END;

CREATE TRIGGER search_safety_update AFTER UPDATE ON "safety" BEGIN
    DELETE FROM search WHERE kind = 'safety' AND row_id = OLD.id;
    INSERT INTO search (kind, row_id, monograph_id, title, body)
    VALUES ('safety', NEW.id, NEW.monograph_id, coalesce(NEW.finding, ''),
            trim(coalesce(NEW."kind", '') || ' ' || coalesce(NEW."severity", '') || ' ' || coalesce(NEW."source_note", '')));
END;

CREATE TRIGGER search_safety_delete AFTER DELETE ON "safety" BEGIN
    DELETE FROM search WHERE kind = 'safety' AND row_id = OLD.id;
END;

-- Deleting a record cascades its claim rows away. SQLite only fires triggers
-- for cascaded deletes when recursive_triggers is on, and that pragma is
-- per-connection — so the search rows are swept here instead, where it holds
-- however the caller opened the database.
CREATE TRIGGER search_monograph_sweep AFTER DELETE ON monograph BEGIN
    DELETE FROM search WHERE monograph_id = OLD.id;
END;

-- Backfill: this migration may land on a database that already has records.

INSERT INTO search (kind, row_id, monograph_id, title, body)
    SELECT 'monograph', id, id, coalesce("accepted_name", ''),
           trim(coalesce("authority", '') || ' ' || coalesce("family", '') || ' ' || coalesce("part", '') || ' ' || coalesce("habitat_note", '') || ' ' || coalesce("summary", '') || ' ' || coalesce("preparation", ''))
      FROM "monograph";
INSERT INTO search (kind, row_id, monograph_id, title, body)
    SELECT 'reference', id, NULL, coalesce("title", ''),
           trim(coalesce("authors", '') || ' ' || coalesce("journal", '') || ' ' || coalesce("doi", '') || ' ' || coalesce("isbn", '') || ' ' || coalesce("why_it_mattered", ''))
      FROM "reference";
INSERT INTO search (kind, row_id, monograph_id, title, body)
    SELECT 'output', id, NULL, coalesce("title", ''),
           trim(coalesce("kind", '') || ' ' || coalesce("venue", '') || ' ' || coalesce("url", ''))
      FROM "output";
INSERT INTO search (kind, row_id, monograph_id, title, body)
    SELECT 'vernacular', id, monograph_id, coalesce("name", ''),
           trim(coalesce("language", '') || ' ' || coalesce("region", '') || ' ' || coalesce("source_note", ''))
      FROM "vernacular";
INSERT INTO search (kind, row_id, monograph_id, title, body)
    SELECT 'indication', id, monograph_id, coalesce("condition", ''),
           trim(coalesce("tradition", '') || ' ' || coalesce("region", '') || ' ' || coalesce("evidence", '') || ' ' || coalesce("source_note", ''))
      FROM "indication";
INSERT INTO search (kind, row_id, monograph_id, title, body)
    SELECT 'constituent', id, monograph_id, coalesce("compound", ''),
           trim(coalesce("class", '') || ' ' || coalesce("inchikey", '') || ' ' || coalesce("source_note", ''))
      FROM "constituent";
INSERT INTO search (kind, row_id, monograph_id, title, body)
    SELECT 'safety', id, monograph_id, coalesce("finding", ''),
           trim(coalesce("kind", '') || ' ' || coalesce("severity", '') || ' ' || coalesce("source_note", ''))
      FROM "safety";
