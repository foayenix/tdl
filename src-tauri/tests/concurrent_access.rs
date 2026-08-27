//! §7 test 2 — concurrent access. Never delete this test.
//!
//! "Rust core and a `ledger` process write to the same database in one test,
//! both under WAL, neither raises `database is locked`."
//!
//! This is the test that proves the two-process architecture actually works.
//! Both sides must open WAL and a busy timeout; if either forgets, this fails.

use std::path::{Path, PathBuf};
use std::process::Command;

use ledger_app::{open, open_checked, user_version, Error, SCHEMA_VERSION};

/// The interpreter that runs the CLI. `LEDGER_PYTHON` wins; otherwise the
/// repo's development venv, which is what `just check` builds.
fn python() -> PathBuf {
    if let Some(given) = std::env::var_os("LEDGER_PYTHON") {
        return PathBuf::from(given);
    }

    let venv = repo_root().join(".venv/bin/python");
    if venv.exists() {
        return venv;
    }

    PathBuf::from("python3")
}

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("src-tauri has a parent")
        .to_path_buf()
}

/// Run `ledger …` against `database`, returning its stdout.
fn ledger(database: &Path, args: &[&str]) -> String {
    let output = Command::new(python())
        .current_dir(repo_root())
        .arg("-m")
        .arg("ledger")
        .arg("--db")
        .arg(database)
        .args(args)
        .output()
        .expect("the ledger CLI could not be started");

    let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
    assert!(
        output.status.success(),
        "ledger {args:?} failed\nstdout: {stdout}\nstderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    stdout
}

struct Scratch(PathBuf);

impl Scratch {
    fn new(name: &str) -> Self {
        let dir = std::env::temp_dir().join(format!("ledger-test-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).expect("scratch directory");
        Scratch(dir)
    }

    fn database(&self) -> PathBuf {
        self.0.join("ledger.sqlite")
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn both_processes_write_to_one_database_without_locking() {
    let scratch = Scratch::new("concurrent");
    let database = scratch.database();

    ledger(&database, &["migrate"]);

    // The Rust side holds an open connection for the whole test — this is the
    // app being open on the desktop while you work in the terminal.
    let connection = open_checked(&database).expect("the app opens the ledger");

    for day in 1..=10 {
        // The app writes.
        connection
            .execute(
                "INSERT INTO monograph (accepted_name) VALUES (?1)",
                [format!("Test record {day}")],
            )
            .unwrap_or_else(|error| panic!("the app could not write: {error}"));

        // The CLI writes, to the same file, while that connection is open.
        ledger(
            &database,
            &[
                "log",
                "--date",
                &format!("2026-08-{day:02}"),
                "--minutes",
                "30",
                "--note",
                "concurrent write",
            ],
        );

        // And the app reads back what the CLI just wrote.
        let entries: i64 = connection
            .query_row("SELECT count(*) FROM entry", [], |row| row.get(0))
            .expect("the app reads the CLI's writes");
        assert_eq!(entries, day as i64);
    }

    let records: i64 = connection
        .query_row("SELECT count(*) FROM monograph", [], |row| row.get(0))
        .unwrap();
    assert_eq!(records, 10);
}

#[test]
fn the_app_opens_in_wal_with_a_busy_timeout_and_foreign_keys() {
    let scratch = Scratch::new("pragmas");
    let database = scratch.database();
    ledger(&database, &["migrate"]);

    let connection = open(&database).unwrap();

    let journal: String = connection
        .query_row("PRAGMA journal_mode", [], |row| row.get(0))
        .unwrap();
    assert_eq!(journal.to_lowercase(), "wal");

    let timeout: i64 = connection
        .query_row("PRAGMA busy_timeout", [], |row| row.get(0))
        .unwrap();
    assert_eq!(timeout, ledger_app::BUSY_TIMEOUT_MS);

    let foreign_keys: i64 = connection
        .query_row("PRAGMA foreign_keys", [], |row| row.get(0))
        .unwrap();
    assert_eq!(foreign_keys, 1, "without this the links are decorative");
}

#[test]
fn the_app_refuses_a_schema_it_was_not_compiled_against() {
    let scratch = Scratch::new("guard");
    let database = scratch.database();
    ledger(&database, &["migrate"]);

    assert_eq!(
        user_version(&open(&database).unwrap()).unwrap(),
        SCHEMA_VERSION
    );

    // Pretend a later migration has run that this build knows nothing about.
    {
        let connection = open(&database).unwrap();
        connection
            .pragma_update(None, "user_version", SCHEMA_VERSION + 1)
            .unwrap();
    }

    match open_checked(&database) {
        Err(Error::SchemaMismatch { found, expected }) => {
            assert_eq!(found, SCHEMA_VERSION + 1);
            assert_eq!(expected, SCHEMA_VERSION);
        }
        other => panic!("expected a schema mismatch, got {other:?}"),
    }
}

#[test]
fn the_app_refuses_a_database_that_is_not_there() {
    let scratch = Scratch::new("absent");
    match open_checked(&scratch.database()) {
        Err(Error::NoDatabase(path)) => assert_eq!(path, scratch.database()),
        other => panic!("expected NoDatabase, got {other:?}"),
    }
}

#[test]
fn the_app_refuses_an_unmigrated_file() {
    let scratch = Scratch::new("unmigrated");
    let database = scratch.database();
    drop(open(&database).unwrap()); // creates the file at user_version 0

    match open_checked(&database) {
        Err(Error::SchemaMismatch { found, .. }) => assert_eq!(found, 0),
        other => panic!("expected a schema mismatch, got {other:?}"),
    }
}

#[test]
fn the_sourcing_invariant_holds_against_the_app_too() {
    // The triggers are in the database, not in either language's code — so the
    // Rust side is bound by them exactly as the CLI is.
    let scratch = Scratch::new("invariant");
    let database = scratch.database();
    ledger(&database, &["migrate"]);

    let connection = open_checked(&database).unwrap();
    connection
        .execute(
            "INSERT INTO monograph (id, accepted_name) VALUES (1, 'Test record')",
            [],
        )
        .unwrap();
    connection
        .execute(
            "INSERT INTO indication (monograph_id, condition) VALUES (1, 'a condition')",
            [],
        )
        .unwrap();

    let refused = connection.execute("UPDATE monograph SET status = 'reviewed' WHERE id = 1", []);
    assert!(
        refused.is_err(),
        "the app walked around the sourcing invariant"
    );

    let status: String = connection
        .query_row("SELECT status FROM monograph WHERE id = 1", [], |row| {
            row.get(0)
        })
        .unwrap();
    assert_eq!(status, "skeleton");
}
