//! Dump every command response for one ledger as JSON, for the browser preview.
//!
//! It calls the **same functions the window calls**, so the preview cannot
//! drift from the app: if a query changes, this changes with it. A development
//! tool; it is not part of the shipped binary.
//!
//!     cargo run --bin preview_dump -- /tmp/demo.sqlite > preview.json

use std::path::PathBuf;

use ledger_app as ledger;
use serde_json::{json, Map, Value};

fn main() {
    let path = PathBuf::from(
        std::env::args()
            .nth(1)
            .expect("usage: preview_dump <ledger.sqlite>"),
    );

    let corpus = ledger::corpus(&path).expect("corpus");

    // One entry per monograph, keyed by id, so the stub can answer a record
    // request without a round trip.
    let mut records = Map::new();
    for row in &corpus.rows {
        let id = row.id;

        let mut claims = Map::new();
        for table in ["vernacular", "indication", "constituent", "safety"] {
            claims.insert(
                table.to_string(),
                json!(ledger::claims(&path, id, table).unwrap_or_default()),
            );
        }

        let mut sources = Map::new();
        for section in ["summary", "preparation"] {
            sources.insert(
                section.to_string(),
                json!(ledger::section_sources(&path, id, section).unwrap_or_default()),
            );
        }

        records.insert(
            id.to_string(),
            json!({
                "record": ledger::record(&path, id).expect("record"),
                "claims": claims,
                "section_sources": sources,
                "references": ledger::record_references(&path, id).unwrap_or_default(),
                "cited_by_outputs": ledger::cited_by_outputs(&path, id).unwrap_or_default(),
                "queued_reading": ledger::queued_reading(&path, id).ok(),
                "unsourced_by_section": ledger::unsourced_by_section(&path, id).unwrap_or_default(),
                "benefit_sharing": ledger::benefit_sharing(&path, id).ok(),
                "queue_position": ledger::queue_position(&path, id).ok().flatten(),
            }),
        );
    }

    let dump: Value = json!({
        "status": ledger::status(&path).expect("status"),
        "nav_counts": ledger::nav_counts(&path).expect("nav counts"),
        "today": ledger::today_stats(&path).expect("today"),
        "note": ledger::note_for_today(&path).expect("note"),
        "day_log": ledger::day_log(&path, 14).expect("day log"),
        "corpus": corpus,
        "wall": ledger::wall(&path).expect("wall"),
        "broken_streak": ledger::broken_streak(&path).expect("broken streak"),
        "next_skeleton": ledger::next_skeleton(&path).expect("next skeleton"),
        "records": records,
    });

    println!("{}", serde_json::to_string(&dump).expect("json"));
}
