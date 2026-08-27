// The window. Everything the frontend can ask for goes through a command here;
// the frontend itself holds no shell permission and never touches the database.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;

use ledger_app::{
    default_path, nav_counts, set_floor_day, status, today_stats, NavCounts, Status, TodayStats,
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

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            ledger_status,
            ledger_nav_counts,
            ledger_today,
            ledger_set_floor_day
        ])
        .run(tauri::generate_context!())
        .expect("the ledger window could not start");
}
