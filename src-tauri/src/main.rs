// The window. Everything the frontend can ask for goes through a command here;
// the frontend itself holds no shell permission and never touches the database.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::time::{Duration, Instant};

use tauri_plugin_shell::ShellExt;

use ledger_app::{
    add_claim, add_output, benefit_sharing, broken_streak, cited_by_outputs, claims, corpus,
    day_log, default_path, nav_counts, nearest_name, next_skeleton, note_for_today, open_monograph,
    parse_fetch, parse_resolution, queue_position, queued_reading, record, record_references,
    save_benefit_sharing, save_note, save_prose, search, section_sources, set_floor_day,
    set_name_by_hand, status, today_stats, unsourced_by_section, BenefitSharing, BoundReference,
    BrokenStreak, CitingOutput, Claim, Corpus, DayLog, FetchResult, NavCounts, QueuePosition,
    QueuedReading, Record, Resolution, SavedNote, SearchResult, Status, TodayStats,
};

/// Where this build reads the ledger from. `LEDGER_DB` overrides it, which is
/// how the app is pointed at a scratch file during development.
fn ledger_path() -> PathBuf {
    std::env::var_os("LEDGER_DB")
        .map(PathBuf::from)
        .unwrap_or_else(default_path)
}

#[tauri::command]
fn ledger_status() -> std::result::Result<Status, String> {
    status(&ledger_path()).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_nav_counts() -> std::result::Result<NavCounts, String> {
    nav_counts(&ledger_path()).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_today() -> std::result::Result<TodayStats, String> {
    today_stats(&ledger_path()).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_set_floor_day(floor_day: bool) -> std::result::Result<TodayStats, String> {
    set_floor_day(&ledger_path(), floor_day).map_err(|error| error.to_string())
}

/// Artboard 02's table is the last fourteen days.
const DAY_LOG_SPAN: i64 = 14;

/// Every sidecar call has a timeout (BUILD.md §3). Crossref's own polite-pool
/// latency is well inside this; anything past it is a network that is not
/// coming back, and the row says so rather than spinning.
const SIDECAR_TIMEOUT: Duration = Duration::from_secs(20);

/// `Fetch` — resolve a DOI through the frozen `ledger` binary.
///
/// The frontend never holds shell permission; the invocation is here, and the
/// capability grants exactly one sidecar (BUILD.md §3).
#[tauri::command]
async fn ledger_fetch_reference(
    app: tauri::AppHandle,
    doi: String,
) -> std::result::Result<FetchResult, String> {
    let database = ledger_path();
    let started = Instant::now();

    let command = app
        .shell()
        .sidecar("ledger")
        .map_err(|error| format!("the ledger sidecar is not available: {error}"))?
        .args([
            "--db",
            &database.to_string_lossy(),
            "ref",
            doi.trim(),
            "--json",
        ]);

    let output = match tokio::time::timeout(SIDECAR_TIMEOUT, command.output()).await {
        Err(_) => {
            return Ok(FetchResult {
                ok: false,
                reference_id: None,
                title: None,
                message: format!(
                    "Crossref did not answer within {}s — the DOI was not kept, try again",
                    SIDECAR_TIMEOUT.as_secs()
                ),
            })
        }
        Ok(Err(error)) => return Err(format!("the ledger sidecar could not run: {error}")),
        Ok(Ok(output)) => output,
    };

    let stdout = String::from_utf8_lossy(&output.stdout);
    let elapsed = started.elapsed().as_millis();

    // The CLI prints its failures to stdout as JSON; stderr means it fell over.
    if stdout.trim().is_empty() && !output.stderr.is_empty() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Ok(parse_fetch(&stderr, elapsed));
    }

    Ok(parse_fetch(&stdout, elapsed))
}

/// Resolve a record's name against GBIF, through the sidecar.
///
/// Same shape as `Fetch`: enrichment is Python's and Rust has no HTTP client.
/// Below the threshold the CLI writes nothing to `accepted_name` and reports
/// the candidates instead — this end only reads what it said.
#[tauri::command]
async fn ledger_resolve_name(
    app: tauri::AppHandle,
    name: String,
    accept: bool,
) -> std::result::Result<Resolution, String> {
    let database = ledger_path();

    let mut args = vec![
        "--db".to_string(),
        database.to_string_lossy().into_owned(),
        "resolve".to_string(),
        name.trim().to_string(),
        "--json".to_string(),
    ];
    if accept {
        // Artboard 08 state 4's `Accept top match`. A person deciding is not
        // the machine guessing.
        args.push("--accept".to_string());
    }

    let command = app
        .shell()
        .sidecar("ledger")
        .map_err(|error| format!("the ledger sidecar is not available: {error}"))?
        .args(args);

    let output = match tokio::time::timeout(SIDECAR_TIMEOUT, command.output()).await {
        Err(_) => {
            return Ok(Resolution {
                reason: format!(
                    "GBIF did not answer within {}s — nothing was written",
                    SIDECAR_TIMEOUT.as_secs()
                ),
                ..Resolution::default()
            })
        }
        Ok(Err(error)) => return Err(format!("the ledger sidecar could not run: {error}")),
        Ok(Ok(output)) => output,
    };

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let text = if stdout.trim().is_empty() {
        stderr.as_ref()
    } else {
        stdout.as_ref()
    };

    Ok(parse_resolution(text))
}

#[tauri::command]
fn ledger_set_name_by_hand(id: i64, name: String) -> std::result::Result<Record, String> {
    set_name_by_hand(&ledger_path(), id, &name).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_day_log() -> std::result::Result<DayLog, String> {
    day_log(&ledger_path(), DAY_LOG_SPAN).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_corpus() -> std::result::Result<Corpus, String> {
    corpus(&ledger_path()).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_broken_streak() -> std::result::Result<Option<BrokenStreak>, String> {
    broken_streak(&ledger_path()).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_queue_position(id: i64) -> std::result::Result<Option<QueuePosition>, String> {
    queue_position(&ledger_path(), id).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_next_skeleton() -> std::result::Result<Option<i64>, String> {
    next_skeleton(&ledger_path()).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_record_references(id: i64) -> std::result::Result<Vec<BoundReference>, String> {
    record_references(&ledger_path(), id).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_cited_by_outputs(id: i64) -> std::result::Result<Vec<CitingOutput>, String> {
    cited_by_outputs(&ledger_path(), id).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_queued_reading(id: i64) -> std::result::Result<QueuedReading, String> {
    queued_reading(&ledger_path(), id).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_unsourced_by_section(id: i64) -> std::result::Result<Vec<(String, i64)>, String> {
    unsourced_by_section(&ledger_path(), id).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_benefit_sharing(id: i64) -> std::result::Result<BenefitSharing, String> {
    benefit_sharing(&ledger_path(), id).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_save_benefit_sharing(
    id: i64,
    narrative: Option<String>,
    agreement_ref: Option<String>,
    expires: Option<String>,
) -> std::result::Result<BenefitSharing, String> {
    save_benefit_sharing(&ledger_path(), id, narrative, agreement_ref, expires)
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_save_prose(id: i64, field: String, text: String) -> std::result::Result<Record, String> {
    save_prose(&ledger_path(), id, &field, &text).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_section_sources(id: i64, section: String) -> std::result::Result<Vec<i64>, String> {
    section_sources(&ledger_path(), id, &section).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_claims(id: i64, table: String) -> std::result::Result<Vec<Claim>, String> {
    claims(&ledger_path(), id, &table).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_add_claim(
    id: i64,
    table: String,
    values: Vec<String>,
    source_note: Option<String>,
) -> std::result::Result<i64, String> {
    add_claim(&ledger_path(), id, &table, values, source_note).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_record(id: i64) -> std::result::Result<Record, String> {
    record(&ledger_path(), id).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_search(query: String) -> std::result::Result<SearchResult, String> {
    search(&ledger_path(), &query).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_nearest_name(query: String) -> std::result::Result<Option<(String, usize)>, String> {
    nearest_name(&ledger_path(), &query).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_note() -> std::result::Result<SavedNote, String> {
    note_for_today(&ledger_path()).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_save_note(note: String) -> std::result::Result<SavedNote, String> {
    save_note(&ledger_path(), &note).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_open_monograph(name: String) -> std::result::Result<i64, String> {
    open_monograph(&ledger_path(), &name).map_err(|error| error.to_string())
}

#[tauri::command]
fn ledger_add_output(kind: String, title: String) -> std::result::Result<i64, String> {
    add_output(&ledger_path(), &kind, &title).map_err(|error| error.to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            ledger_status,
            ledger_nav_counts,
            ledger_today,
            ledger_set_floor_day,
            ledger_note,
            ledger_save_note,
            ledger_open_monograph,
            ledger_add_output,
            ledger_day_log,
            ledger_fetch_reference,
            ledger_corpus,
            ledger_search,
            ledger_nearest_name,
            ledger_record,
            ledger_claims,
            ledger_add_claim,
            ledger_benefit_sharing,
            ledger_save_benefit_sharing,
            ledger_save_prose,
            ledger_section_sources,
            ledger_record_references,
            ledger_cited_by_outputs,
            ledger_queued_reading,
            ledger_unsourced_by_section,
            ledger_broken_streak,
            ledger_queue_position,
            ledger_next_skeleton,
            ledger_resolve_name,
            ledger_set_name_by_hand
        ])
        .run(tauri::generate_context!())
        .expect("the ledger window could not start");
}
