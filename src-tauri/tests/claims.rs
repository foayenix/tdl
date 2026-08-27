//! Reading and adding claim rows — the record's inline `+ add`.

use std::path::{Path, PathBuf};
use std::process::Command;

use ledger_app::{add_claim, claim_columns, claims, open_checked, record};

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

struct Scratch(PathBuf);

impl Scratch {
    fn new(name: &str) -> Self {
        let dir = std::env::temp_dir().join(format!("ledger-claims-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).expect("scratch directory");
        Scratch(dir)
    }

    /// A migrated database with one monograph, id 1.
    fn database(&self) -> PathBuf {
        let database = self.0.join("ledger.sqlite");
        let output = Command::new(python())
            .current_dir(repo_root())
            .args(["-m", "ledger", "--db"])
            .arg(&database)
            .arg("migrate")
            .output()
            .expect("the ledger CLI could not be started");
        assert!(output.status.success());

        let connection = open_checked(&database).expect("open");
        connection
            .execute(
                "INSERT INTO monograph (id, accepted_name) VALUES (1, 'Khaya senegalensis')",
                [],
            )
            .unwrap();
        database
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn the_claim_columns_match_the_python_side() {
    // `ledger.claims.CLAIM_TABLES` is the twin of `claim_columns`.
    let output = Command::new(python())
        .current_dir(repo_root())
        .arg("-c")
        .arg(
            "import json\nfrom ledger.claims import CLAIM_TABLES\n\
             print(json.dumps({k: list(v) for k, v in CLAIM_TABLES.items()}))",
        )
        .output()
        .expect("python could not be started");

    let from_python: serde_json::Value =
        serde_json::from_slice(&output.stdout).expect("python printed JSON");

    for table in ["vernacular", "indication", "constituent", "safety"] {
        let expected: Vec<String> = from_python[table]
            .as_array()
            .unwrap_or_else(|| panic!("{table} missing on the Python side"))
            .iter()
            .map(|value| value.as_str().unwrap().to_string())
            .collect();

        let actual: Vec<String> = claim_columns(table)
            .unwrap_or_else(|| panic!("{table} missing on the Rust side"))
            .iter()
            .map(|column| column.to_string())
            .collect();

        assert_eq!(actual, expected, "{table} columns differ between the two");
    }
}

#[test]
fn an_added_row_reads_back_in_order() {
    let scratch = Scratch::new("add");
    let database = scratch.database();

    add_claim(
        &database,
        1,
        "vernacular",
        vec!["kuka".into(), "Hausa".into(), "northern Nigeria".into()],
        Some("field notes 2025-11".into()),
    )
    .expect("add");

    let rows = claims(&database, 1, "vernacular").expect("read");
    assert_eq!(rows.len(), 1);
    assert_eq!(
        rows[0].cells,
        vec![
            Some("kuka".to_string()),
            Some("Hausa".to_string()),
            Some("northern Nigeria".to_string())
        ]
    );
    assert_eq!(rows[0].source_note.as_deref(), Some("field notes 2025-11"));
    assert!(!rows[0].is_unsourced());
}

#[test]
fn a_row_added_without_a_source_is_unsourced_and_says_so() {
    let scratch = Scratch::new("unsourced");
    let database = scratch.database();

    add_claim(
        &database,
        1,
        "vernacular",
        vec!["kuka".into(), "".into(), "".into()],
        None,
    )
    .expect("add");

    let rows = claims(&database, 1, "vernacular").expect("read");
    assert!(rows[0].is_unsourced());
    // A blank optional column is NULL, not an empty string.
    assert_eq!(rows[0].cells[1], None);

    // And it follows into the record header.
    assert_eq!(record(&database, 1).expect("record").unsourced, 1);
}

#[test]
fn whitespace_is_not_a_source() {
    let scratch = Scratch::new("whitespace");
    let database = scratch.database();

    add_claim(
        &database,
        1,
        "vernacular",
        vec!["kuka".into(), "".into(), "".into()],
        Some("   ".into()),
    )
    .expect("add");

    assert!(claims(&database, 1, "vernacular").expect("read")[0].is_unsourced());
}

#[test]
fn a_row_needs_its_first_column() {
    let scratch = Scratch::new("blank");
    let database = scratch.database();

    let refused = add_claim(
        &database,
        1,
        "vernacular",
        vec!["  ".into(), "".into(), "".into()],
        None,
    );
    assert_eq!(
        refused.unwrap_err().to_string(),
        "a vernacular row needs a name"
    );
}

#[test]
fn the_wrong_number_of_values_is_refused() {
    let scratch = Scratch::new("arity");
    let database = scratch.database();

    let refused = add_claim(&database, 1, "vernacular", vec!["kuka".into()], None);
    assert!(refused
        .unwrap_err()
        .to_string()
        .contains("takes 3 values, got 1"));
}

#[test]
fn an_invented_claim_table_is_refused() {
    let scratch = Scratch::new("table");
    let database = scratch.database();

    assert!(claims(&database, 1, "folklore").is_err());
    assert!(add_claim(&database, 1, "folklore", vec!["x".into()], None).is_err());
}

#[test]
fn a_reviewed_record_refuses_an_unsourced_row_in_words() {
    // The trigger from session 06 is what actually refuses it; this turns the
    // SQL error into a sentence the record can show.
    let scratch = Scratch::new("reviewed");
    let database = scratch.database();
    let connection = open_checked(&database).expect("open");
    connection
        .execute("UPDATE monograph SET status = 'reviewed' WHERE id = 1", [])
        .unwrap();

    let refused = add_claim(
        &database,
        1,
        "indication",
        vec![
            "fever".into(),
            "".into(),
            "".into(),
            "traditional_only".into(),
        ],
        None,
    );

    assert_eq!(
        refused.unwrap_err().to_string(),
        "a reviewed monograph cannot take an unsourced row — source it first"
    );

    // A sourced row still goes in.
    add_claim(
        &database,
        1,
        "indication",
        vec![
            "fever".into(),
            "".into(),
            "".into(),
            "traditional_only".into(),
        ],
        Some("R1".into()),
    )
    .expect("sourced rows are fine");
}

#[test]
fn an_indication_defaults_to_traditional_only_when_no_level_is_given() {
    let scratch = Scratch::new("evidence_default");
    let database = scratch.database();

    // The inline add leaves `evidence` blank; the column's DEFAULT decides.
    let refused = add_claim(
        &database,
        1,
        "indication",
        vec!["fever".into(), "".into(), "".into(), "".into()],
        Some("R1".into()),
    );

    // An empty string is not one of the six levels, so the CHECK refuses it —
    // the interface must send a level, not a blank.
    assert!(
        refused.is_err(),
        "a blank evidence level must not be stored"
    );
}
