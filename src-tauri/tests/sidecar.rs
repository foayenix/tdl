//! Reading what the sidecar said.
//!
//! The shapes come from `ledger/commands/ref.py` — the fixtures below are its
//! actual output, not guesses. The shell invocation itself needs a running
//! Tauri app; this covers the part that decides what the interface tells you.

use ledger_app::parse_fetch;

#[test]
fn a_resolved_reference_reports_how_long_it_took() {
    let stdout = r#"{
      "id": 7,
      "doi": "10.1016/j.jep.2019.112202",
      "title": "PLACEHOLDER TITLE",
      "read_state": "queued",
      "added_from": "crossref"
    }"#;

    let result = parse_fetch(stdout, 240);

    assert!(result.ok);
    assert_eq!(result.reference_id, Some(7));
    assert_eq!(result.title.as_deref(), Some("PLACEHOLDER TITLE"));
    assert_eq!(result.message, "resolved in 240 ms");
}

#[test]
fn an_unreachable_network_is_not_a_success_but_keeps_the_row() {
    let stdout = r#"{
      "id": 7,
      "doi": "10.1016/j.jep.2019.112202",
      "title": "10.1016/j.jep.2019.112202",
      "added_from": "offline",
      "note": "could not reach Crossref: timed out — kept as unresolved, run again later"
    }"#;

    let result = parse_fetch(stdout, 10_000);

    assert!(!result.ok, "a kept DOI is not a resolved reference");
    assert_eq!(result.reference_id, Some(7), "the row is still there");
    assert!(result.message.contains("kept as unresolved"));
}

#[test]
fn a_doi_that_is_not_a_doi_says_so() {
    let result = parse_fetch(r#"{"error": "'not a doi' is not a DOI"}"#, 1);

    assert!(!result.ok);
    assert_eq!(result.reference_id, None);
    assert_eq!(result.message, "'not a doi' is not a DOI");
}

#[test]
fn a_doi_crossref_has_never_heard_of_says_so() {
    let stdout = r#"{"doi": "10.5555/nope", "error": "Crossref has no record of 10.5555/nope"}"#;
    let result = parse_fetch(stdout, 120);

    assert!(!result.ok);
    assert!(result.message.contains("no record of"));
}

#[test]
fn a_reference_already_in_the_library_is_reported_as_such() {
    let stdout = r#"{"id": 7, "title": "PLACEHOLDER TITLE", "note": "already in the library"}"#;
    let result = parse_fetch(stdout, 3);

    assert!(!result.ok, "nothing new was fetched");
    assert_eq!(result.reference_id, Some(7));
    assert_eq!(result.message, "already in the library");
}

#[test]
fn output_that_is_not_json_still_produces_a_line() {
    let result = parse_fetch("Traceback (most recent call last):\n  File ...", 5);

    assert!(!result.ok);
    assert_eq!(result.message, "Traceback (most recent call last):");
}

#[test]
fn a_silent_sidecar_still_produces_a_line() {
    // Every sidecar call has a visible inline failure state (BUILD.md §3).
    let result = parse_fetch("   \n", 5);

    assert!(!result.ok);
    assert_eq!(result.message, "the sidecar said nothing");
}

// ── artboard 08 state 4: what `ledger resolve --json` says ──────────────

use ledger_app::parse_resolution;

#[test]
fn a_below_threshold_match_reports_its_candidates() {
    // The shape `ledger/commands/resolve.py` prints.
    let stdout = r#"[
      {
        "monograph_id": 4,
        "name": "Sutherlandia frutescens",
        "accepted": false,
        "reason": "below the 0.90 threshold",
        "confidence": 0.42,
        "gbif_key": null,
        "candidates": [
          {"name": "PLACEHOLDER CANDIDATE TWO", "gbif_key": 5000002, "confidence": 0.38},
          {"name": "PLACEHOLDER CANDIDATE THREE", "gbif_key": 5000003, "confidence": 0.31}
        ]
      }
    ]"#;

    let resolution = parse_resolution(stdout);

    assert!(!resolution.accepted);
    assert_eq!(resolution.reason, "below the 0.90 threshold");
    assert_eq!(resolution.confidence, Some(0.42));
    assert_eq!(resolution.candidates.len(), 2);
    assert_eq!(resolution.candidates[0].gbif_key, Some(5000002));
    assert_eq!(resolution.candidates[0].confidence, 0.38);
}

#[test]
fn a_resolved_name_carries_no_candidates() {
    let stdout = r#"[{"monograph_id": 1, "name": "Khaya senegalensis", "accepted": true,
                      "reason": "resolved", "confidence": 0.97, "gbif_key": 3190368,
                      "candidates": []}]"#;

    let resolution = parse_resolution(stdout);

    assert!(resolution.accepted);
    assert!(resolution.candidates.is_empty());
    assert_eq!(resolution.name.as_deref(), Some("Khaya senegalensis"));
}

#[test]
fn a_sidecar_that_fell_over_still_produces_a_reason() {
    let resolution = parse_resolution("Traceback (most recent call last):\n  File ...");

    assert!(!resolution.accepted);
    assert_eq!(resolution.reason, "Traceback (most recent call last):");
    assert!(resolution.candidates.is_empty());
}
