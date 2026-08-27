//! The writes artboard 02's note and deposit rows perform.
//!
//! Simple writes are Rust's, per BUILD.md §3's ownership rule. Anything that
//! touches the network — `Fetch` — is the sidecar's and is not here.

use std::path::{Path, PathBuf};
use std::process::Command;

use ledger_app::{add_output, note_for_today, open_checked, open_monograph, save_note};

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("src-tauri has a parent")
        .to_path_buf()
}

fn python() -> PathBuf {
    if let Some(given) = std::env::var_os("LEDGER_PYTHON") {
        return PathBuf::from(given);
    }
    let venv = repo_root().join(".venv/bin/python");
    if venv.exists() {
        venv
    } else {
        PathBuf::from("python3")
    }
}

fn migrate(database: &Path) {
    let output = Command::new(python())
        .current_dir(repo_root())
        .args(["-m", "ledger", "--db"])
        .arg(database)
        .arg("migrate")
        .output()
        .expect("the ledger CLI could not be started");
    assert!(output.status.success());
}

struct Scratch(PathBuf);

impl Scratch {
    fn new(name: &str) -> Self {
        let dir =
            std::env::temp_dir().join(format!("ledger-deposit-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).expect("scratch directory");
        Scratch(dir)
    }

    fn database(&self) -> PathBuf {
        let database = self.0.join("ledger.sqlite");
        migrate(&database);
        database
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn the_note_reads_back_what_was_written() {
    let scratch = Scratch::new("note");
    let database = scratch.database();

    let empty = note_for_today(&database).expect("read");
    assert_eq!(empty.note, "");
    assert_eq!(empty.entry_id, 0, "an unopened day has no entry to report");

    let saved = save_note(&database, "Reworked the indication list.").expect("write");
    assert!(saved.entry_id > 0);
    assert_eq!(saved.saved_at.len(), 5, "the footer clock is HH:MM");

    let read = note_for_today(&database).expect("read");
    assert_eq!(read.note, "Reworked the indication list.");
    assert_eq!(read.entry_id, saved.entry_id);
}

#[test]
fn autosaving_repeatedly_writes_one_entry() {
    let scratch = Scratch::new("autosave");
    let database = scratch.database();

    for text in ["R", "Re", "Rew", "Rewo"] {
        save_note(&database, text).expect("write");
    }

    let connection = open_checked(&database).expect("open");
    let days: i64 = connection
        .query_row("SELECT count(*) FROM entry", [], |row| row.get(0))
        .unwrap();
    assert_eq!(days, 1);
    assert_eq!(note_for_today(&database).expect("read").note, "Rewo");
}

#[test]
fn the_note_may_be_emptied() {
    let scratch = Scratch::new("empty_note");
    let database = scratch.database();

    save_note(&database, "something").expect("write");
    save_note(&database, "").expect("clear");

    assert_eq!(note_for_today(&database).expect("read").note, "");
}

#[test]
fn opening_a_monograph_leaves_the_identifiers_null() {
    let scratch = Scratch::new("mono");
    let database = scratch.database();

    let id = open_monograph(&database, "  Khaya senegalensis  ").expect("open");

    let connection = open_checked(&database).expect("open");
    let (name, status, key): (String, String, Option<i64>) = connection
        .query_row(
            "SELECT accepted_name, status, gbif_key FROM monograph WHERE id = ?1",
            [id],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )
        .unwrap();

    assert_eq!(
        name, "Khaya senegalensis",
        "the name is trimmed, not altered"
    );
    assert_eq!(status, "skeleton");
    assert_eq!(key, None, "that NULL is what puts it in the review queue");
}

#[test]
fn opening_a_monograph_twice_returns_the_same_record() {
    let scratch = Scratch::new("mono_twice");
    let database = scratch.database();

    let first = open_monograph(&database, "Khaya senegalensis").expect("open");
    let second = open_monograph(&database, "Khaya senegalensis").expect("open again");

    assert_eq!(first, second);

    let connection = open_checked(&database).expect("open");
    let count: i64 = connection
        .query_row("SELECT count(*) FROM monograph", [], |row| row.get(0))
        .unwrap();
    assert_eq!(count, 1);
}

#[test]
fn a_monograph_needs_a_name() {
    let scratch = Scratch::new("mono_blank");
    let database = scratch.database();

    let refused = open_monograph(&database, "   ");
    assert!(refused.is_err());
    assert!(refused.unwrap_err().to_string().contains("needs a name"));
}

#[test]
fn an_output_attaches_to_todays_entry() {
    let scratch = Scratch::new("output");
    let database = scratch.database();

    let id = add_output(&database, "note", "Evidence grading").expect("add");

    let connection = open_checked(&database).expect("open");
    let (kind, entry_id): (String, i64) = connection
        .query_row(
            "SELECT o.kind, o.entry_id FROM output o WHERE o.id = ?1",
            [id],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap();

    let today: i64 = connection
        .query_row("SELECT id FROM entry WHERE date = date('now')", [], |row| {
            row.get(0)
        })
        .unwrap();

    assert_eq!(kind, "note");
    assert_eq!(entry_id, today);
}

#[test]
fn an_invented_output_kind_is_refused_in_words() {
    let scratch = Scratch::new("output_kind");
    let database = scratch.database();

    let refused = add_output(&database, "tweet", "A tweet");
    assert_eq!(
        refused.unwrap_err().to_string(),
        "tweet is not an output kind"
    );
}

#[test]
fn an_output_needs_a_title() {
    let scratch = Scratch::new("output_title");
    let database = scratch.database();

    assert!(add_output(&database, "note", "   ").is_err());
}

#[test]
fn two_outputs_on_one_day_share_the_entry() {
    let scratch = Scratch::new("two_outputs");
    let database = scratch.database();

    add_output(&database, "note", "First").expect("add");
    add_output(&database, "talk", "Second").expect("add");

    let connection = open_checked(&database).expect("open");
    let days: i64 = connection
        .query_row("SELECT count(*) FROM entry", [], |row| row.get(0))
        .unwrap();
    let distinct: i64 = connection
        .query_row("SELECT count(DISTINCT entry_id) FROM output", [], |row| {
            row.get(0)
        })
        .unwrap();

    assert_eq!(days, 1);
    assert_eq!(distinct, 1);
}

#[test]
fn the_day_log_returns_a_row_for_every_day_logged_or_not() {
    let scratch = Scratch::new("day_log");
    let database = scratch.database();

    let connection = open_checked(&database).expect("open");
    connection
        .execute(
            "INSERT INTO entry (date, minutes) VALUES (date('now'), 96)",
            [],
        )
        .unwrap();
    connection
        .execute(
            "INSERT INTO entry (date, minutes, floor_day) VALUES (date('now','-3 day'), 20, 1)",
            [],
        )
        .unwrap();

    let log = ledger_app::day_log(&database, 14).expect("log");

    assert_eq!(log.days.len(), 14, "a fortnight is always fourteen rows");
    assert!(log.days[0].is_today);
    assert_eq!(log.days[0].minutes, 96);
    assert_eq!(log.days[1].minutes, 0, "an unlogged day is a row at zero");
    assert_eq!(log.days[3].minutes, 20);
    assert!(log.days[3].floor_day);

    assert_eq!(log.total_minutes, 116);
    assert_eq!(log.average, 116 / 14);
    assert_eq!(log.floor_days, 1);
}

#[test]
fn the_day_log_names_what_was_deposited() {
    let scratch = Scratch::new("day_log_deposits");
    let database = scratch.database();

    open_monograph(&database, "Khaya senegalensis").expect("open");
    open_monograph(&database, "Prunus africana").expect("open");
    add_output(&database, "note", "Evidence grading").expect("add");

    let connection = open_checked(&database).expect("open");
    connection
        .execute(
            "INSERT INTO reference (doi, title) VALUES ('10.1/x', 'A paper')",
            [],
        )
        .unwrap();

    let today = &ledger_app::day_log(&database, 14).expect("log").days[0];

    assert_eq!(
        today.monographs,
        vec![
            "Khaya senegalensis".to_string(),
            "Prunus africana".to_string()
        ]
    );
    assert_eq!(today.references, 1);
    assert_eq!(today.outputs, vec!["note".to_string()]);
}

#[test]
fn a_quiet_fortnight_deposits_nothing() {
    let scratch = Scratch::new("day_log_quiet");
    let database = scratch.database();

    let log = ledger_app::day_log(&database, 14).expect("log");

    assert_eq!(log.total_minutes, 0);
    assert_eq!(log.average, 0);
    assert_eq!(log.floor_days, 0);
    assert!(log.days.iter().all(|day| day.monographs.is_empty()));
}

#[test]
fn a_day_deposited_against_but_not_worked_is_logged_at_zero() {
    // Blank and 0 must not look the same: one day never happened, the other
    // happened and produced an output.
    let scratch = Scratch::new("day_log_zero");
    let database = scratch.database();

    add_output(&database, "note", "Evidence grading").expect("add");

    let today = &ledger_app::day_log(&database, 14).expect("log").days[0];
    assert!(today.logged);
    assert_eq!(today.minutes, 0);

    let yesterday = &ledger_app::day_log(&database, 14).expect("log").days[1];
    assert!(!yesterday.logged);
    assert_eq!(yesterday.minutes, 0);
}
