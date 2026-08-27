//! The streak, in Rust, against the same cases §7 test 7 puts to Python.
//!
//! `current_streak` exists in both languages — BUILD.md §3 says the CLI does
//! these reads directly too. Two implementations of one rule is exactly where
//! drift happens, so this file asserts the Rust answer against the Python
//! answer for every case, on the same database.

use std::path::{Path, PathBuf};
use std::process::Command;

use ledger_app::{open_checked, set_floor_day, today_stats, FLOOR_MINUTES};

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

    assert!(
        output.status.success(),
        "ledger {args:?} failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );

    String::from_utf8_lossy(&output.stdout).into_owned()
}

/// What `ledger.entries.current_streak` says, asked directly.
fn python_streak(database: &Path) -> i64 {
    let output = Command::new(python())
        .current_dir(repo_root())
        .arg("-c")
        .arg(
            "import sys; from ledger.db import connect; from ledger.entries import current_streak;\
             print(current_streak(connect(sys.argv[1])))",
        )
        .arg(database)
        .output()
        .expect("python could not be started");

    String::from_utf8_lossy(&output.stdout)
        .trim()
        .parse()
        .unwrap_or_else(|_| panic!("{}", String::from_utf8_lossy(&output.stderr)))
}

struct Scratch(PathBuf);

impl Scratch {
    fn new(name: &str) -> Self {
        let dir = std::env::temp_dir().join(format!("ledger-streak-{name}-{}", std::process::id()));
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

/// Log entries by how many days back they are from today.
fn log_days_ago(database: &Path, offsets: &[i64], minutes: i64) {
    let connection = open_checked(database).expect("open");
    for offset in offsets {
        connection
            .execute(
                "INSERT INTO entry (date, minutes) VALUES (date('now', ?1), ?2)",
                rusqlite::params![format!("-{offset} day"), minutes],
            )
            .expect("insert entry");
    }
}

fn case(name: &str, offsets: &[i64]) -> (i64, i64) {
    let scratch = Scratch::new(name);
    let database = scratch.database();
    ledger(&database, &["migrate"]);
    log_days_ago(&database, offsets, 30);

    let stats = today_stats(&database).expect("stats");
    let python = python_streak(&database);
    (stats.current_streak, python)
}

#[test]
fn no_entries() {
    let (rust, python) = case("empty", &[]);
    assert_eq!((rust, python), (0, 0));
}

#[test]
fn one_entry_today() {
    let (rust, python) = case("one", &[0]);
    assert_eq!((rust, python), (1, 1));
}

#[test]
fn an_unbroken_run_ending_today() {
    let (rust, python) = case("unbroken", &[4, 3, 2, 1, 0]);
    assert_eq!((rust, python), (5, 5));
}

#[test]
fn gap_yesterday() {
    let (rust, python) = case("gap_yesterday", &[6, 5, 4, 3, 2, 0]);
    assert_eq!((rust, python), (1, 1));
}

#[test]
fn gap_today() {
    let (rust, python) = case("gap_today", &[3, 2, 1]);
    assert_eq!((rust, python), (3, 3));
}

#[test]
fn a_broken_run_reads_zero() {
    // Artboard 08 state 5: three days without an entry reads 0, not 41.
    let (rust, python) = case("broken", &[6, 5, 4]);
    assert_eq!((rust, python), (0, 0));
}

#[test]
fn entries_out_of_order() {
    let (rust, python) = case("out_of_order", &[0, 3, 1, 4, 2]);
    assert_eq!((rust, python), (5, 5));
}

#[test]
fn the_longest_run_survives_a_break() {
    let scratch = Scratch::new("longest");
    let database = scratch.database();
    ledger(&database, &["migrate"]);

    // A run of six, a gap, then a run of two ending today.
    log_days_ago(&database, &[20, 19, 18, 17, 16, 15, 1, 0], 30);

    let stats = today_stats(&database).expect("stats");
    assert_eq!(stats.current_streak, 2);
    assert_eq!(stats.longest_streak, 6);
}

#[test]
fn the_longest_run_of_an_empty_ledger_is_zero() {
    let scratch = Scratch::new("longest_empty");
    let database = scratch.database();
    ledger(&database, &["migrate"]);

    assert_eq!(today_stats(&database).expect("stats").longest_streak, 0);
}

#[test]
fn floor_met_counts_days_that_reached_the_floor() {
    let scratch = Scratch::new("floor");
    let database = scratch.database();
    ledger(&database, &["migrate"]);

    log_days_ago(&database, &[4, 3], FLOOR_MINUTES);
    log_days_ago(&database, &[2, 1], FLOOR_MINUTES - 1);
    log_days_ago(&database, &[0], 96);

    let stats = today_stats(&database).expect("stats");
    assert_eq!(stats.days_logged, 5);
    assert_eq!(stats.floor_met, 3);
    assert_eq!(stats.minutes, 96);
}

#[test]
fn the_floor_toggle_opens_the_day_if_it_is_not_open() {
    let scratch = Scratch::new("toggle");
    let database = scratch.database();
    ledger(&database, &["migrate"]);

    let stats = set_floor_day(&database, true).expect("set");
    assert!(stats.floor_day);
    assert_eq!(stats.minutes, 0);
    assert_eq!(stats.days_logged, 1);

    let stats = set_floor_day(&database, false).expect("unset");
    assert!(!stats.floor_day);
    assert_eq!(
        stats.days_logged, 1,
        "toggling twice must not open two days"
    );
}

#[test]
fn the_floor_toggle_leaves_minutes_alone() {
    let scratch = Scratch::new("toggle_minutes");
    let database = scratch.database();
    ledger(&database, &["migrate"]);
    ledger(&database, &["log", "--minutes", "96"]);

    let stats = set_floor_day(&database, true).expect("set");
    assert_eq!(stats.minutes, 96);
    assert!(stats.floor_day);
}
