//! FTS from the Rust side, and the query tokeniser it shares with Python.
//!
//! `to_match` exists in both languages, like the streak. Every awkward input is
//! asserted against `ledger.find.to_match` on the same string, so the two
//! cannot drift apart into two different ideas of what a search means.

use std::path::{Path, PathBuf};
use std::process::Command;

use ledger_app::{nearest_name, open_checked, search, to_match};

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

/// What `ledger.find.to_match` makes of the same string.
fn python_match(query: &str) -> Option<String> {
    let output = Command::new(python())
        .current_dir(repo_root())
        .arg("-c")
        .arg(
            "import sys\n\
             from ledger.find import to_match\n\
             try:\n    print(to_match(sys.argv[1]), end='')\n\
             except ValueError:\n    sys.exit(3)\n",
        )
        .arg(query)
        .output()
        .expect("python could not be started");

    if output.status.code() == Some(3) {
        None
    } else {
        Some(String::from_utf8_lossy(&output.stdout).into_owned())
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
        let dir = std::env::temp_dir().join(format!("ledger-search-{name}-{}", std::process::id()));
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
fn the_two_tokenisers_agree() {
    for query in [
        "antimalarial bark",
        "bark\"",
        "bark - stem",
        "10.1016/j.jep",
        "NEAR(a b)",
        "stem*",
        "a OR b",
        "Khaya senegalensis",
        "caïlcédrat",
        "  spaced   out  ",
    ] {
        assert_eq!(
            to_match(query),
            python_match(query),
            "the two tokenisers disagree about {query:?}"
        );
    }
}

#[test]
fn a_query_with_no_words_matches_nothing() {
    assert_eq!(to_match("   ---   "), None);
    assert_eq!(python_match("   ---   "), None);
}

#[test]
fn a_claim_hit_lands_on_its_plant() {
    let scratch = Scratch::new("claims");
    let database = scratch.database();
    let connection = open_checked(&database).expect("open");

    connection
        .execute(
            "INSERT INTO monograph (id, accepted_name, family) VALUES (1, 'Khaya senegalensis', 'Meliaceae')",
            [],
        )
        .unwrap();
    connection
        .execute(
            "INSERT INTO indication (monograph_id, condition, source_note)
             VALUES (1, 'malarial fever', 'R1')",
            [],
        )
        .unwrap();

    let found = search(&database, "malarial").expect("search");

    assert_eq!(found.monograph_ids, vec![1]);
    assert_eq!(found.hits, 1);
    assert_eq!(found.monographs_searched, 1);
}

#[test]
fn one_plant_hit_through_several_rows_is_listed_once() {
    let scratch = Scratch::new("dedupe");
    let database = scratch.database();
    let connection = open_checked(&database).expect("open");

    connection
        .execute(
            "INSERT INTO monograph (id, accepted_name, part) VALUES (1, 'Khaya senegalensis', 'stem bark')",
            [],
        )
        .unwrap();
    connection
        .execute(
            "INSERT INTO indication (monograph_id, condition, source_note)
             VALUES (1, 'bark decoction', 'R1')",
            [],
        )
        .unwrap();

    let found = search(&database, "bark").expect("search");

    assert_eq!(found.monograph_ids, vec![1]);
    assert_eq!(found.hits, 2, "the record and the claim are both hits");
}

#[test]
fn syntax_in_the_query_is_searched_for_not_executed() {
    let scratch = Scratch::new("syntax");
    let database = scratch.database();

    for query in ["bark\"", "NEAR(a b)", "a OR b", "10.1016/j.jep", "stem*"] {
        search(&database, query).unwrap_or_else(|error| panic!("{query:?} broke MATCH: {error}"));
    }
}

#[test]
fn an_empty_query_still_reports_what_there_was_to_search() {
    let scratch = Scratch::new("empty");
    let database = scratch.database();
    let connection = open_checked(&database).expect("open");
    connection
        .execute(
            "INSERT INTO monograph (accepted_name) VALUES ('Khaya senegalensis')",
            [],
        )
        .unwrap();

    let found = search(&database, "").expect("search");

    assert_eq!(found.hits, 0);
    assert!(found.monograph_ids.is_empty());
    assert_eq!(found.monographs_searched, 1);
}

#[test]
fn the_nearest_name_is_offered() {
    let scratch = Scratch::new("nearest");
    let database = scratch.database();
    let connection = open_checked(&database).expect("open");
    connection
        .execute(
            "INSERT INTO monograph (accepted_name) VALUES ('Khaya senegalensis')",
            [],
        )
        .unwrap();

    assert_eq!(
        nearest_name(&database, "Khaya senegalense").expect("nearest"),
        Some(("Khaya senegalensis".to_string(), 2))
    );
}

#[test]
fn an_empty_corpus_has_no_nearest_name() {
    let scratch = Scratch::new("nearest_empty");
    let database = scratch.database();

    assert_eq!(
        nearest_name(&database, "Sutherlandia").expect("nearest"),
        None
    );
}
