//! The Rust core: one connection to one SQLite file, opened correctly.
//!
//! Python owns the schema. This side reads `PRAGMA user_version`, refuses to
//! start if it does not match what it was compiled against, and never migrates
//! (BUILD.md §3, ownership rule).

use std::fmt;
use std::path::{Path, PathBuf};

use rusqlite::Connection;
use serde::Serialize;

/// The schema this build was compiled against. Artboard 08's footer shows it.
pub const SCHEMA_VERSION: i64 = 4;

/// Both processes may hold the database open at once (BUILD.md §3).
pub const BUSY_TIMEOUT_MS: i64 = 5000;

#[derive(Debug)]
pub enum Error {
    Sqlite(rusqlite::Error),
    /// The file on disk is not the schema this build knows. Migrating is
    /// Python's job, so the only thing to do here is stop and say so.
    SchemaMismatch {
        found: i64,
        expected: i64,
    },
    NoDatabase(PathBuf),
    /// A write the interface asked for that the record will not take.
    Refused(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Sqlite(error) => write!(f, "{error}"),
            Error::SchemaMismatch { found, expected } => write!(
                f,
                "the ledger is at schema v{found}; this build reads v{expected}. \
                 Run `ledger migrate`."
            ),
            Error::NoDatabase(path) => {
                write!(f, "no ledger at {}. Run `ledger migrate`.", path.display())
            }
            Error::Refused(why) => write!(f, "{why}"),
        }
    }
}

impl std::error::Error for Error {}

impl From<rusqlite::Error> for Error {
    fn from(error: rusqlite::Error) -> Self {
        Error::Sqlite(error)
    }
}

pub type Result<T> = std::result::Result<T, Error>;

/// Where the ledger lives unless told otherwise.
pub fn default_path() -> PathBuf {
    let home = std::env::var_os("HOME")
        .map(PathBuf::from)
        .unwrap_or_default();
    home.join("Documents").join("ledger.sqlite")
}

/// Open a connection with the pragmas the design requires.
///
/// `foreign_keys` is per-connection and is not optional: without it the links
/// between records are decorative, and the sourcing triggers can be walked
/// around. `busy_timeout` is what lets the CLI and the app write at once.
pub fn open(path: &Path) -> Result<Connection> {
    let connection = Connection::open(path)?;
    connection.pragma_update(None, "journal_mode", "WAL")?;
    connection.pragma_update(None, "busy_timeout", BUSY_TIMEOUT_MS)?;
    connection.pragma_update(None, "foreign_keys", true)?;
    Ok(connection)
}

pub fn user_version(connection: &Connection) -> Result<i64> {
    Ok(connection.query_row("PRAGMA user_version", [], |row| row.get(0))?)
}

/// Open a ledger that already exists and is the schema this build reads.
pub fn open_checked(path: &Path) -> Result<Connection> {
    if !path.exists() {
        return Err(Error::NoDatabase(path.to_path_buf()));
    }

    let connection = open(path)?;
    let found = user_version(&connection)?;
    if found != SCHEMA_VERSION {
        return Err(Error::SchemaMismatch {
            found,
            expected: SCHEMA_VERSION,
        });
    }

    Ok(connection)
}

/// What the footer shows: the path, the size on disk, the schema, and when the
/// file was last written — artboard 02's `38.2 MB · saved 14:22`.
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct Status {
    pub path: String,
    pub bytes: u64,
    pub schema_version: i64,
    /// Seconds since the epoch, or None if the filesystem will not say.
    pub last_write: Option<i64>,
}

pub fn status(path: &Path) -> Result<Status> {
    let connection = open_checked(path)?;
    let metadata = std::fs::metadata(path).ok();

    let bytes = metadata.as_ref().map(|meta| meta.len()).unwrap_or(0);
    let last_write = metadata
        .and_then(|meta| meta.modified().ok())
        .and_then(|time| time.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|since| since.as_secs() as i64);

    Ok(Status {
        path: path.display().to_string(),
        bytes,
        schema_version: user_version(&connection)?,
        last_write,
    })
}

/// The floor is 20 minutes. A floor day is a success, and the interface must
/// never render one as a shortfall (DESIGN.md §8, artboard 02).
pub const FLOOR_MINUTES: i64 = 20;

/// BUILD.md §4's streak query, verbatim: the length of the most recent
/// unbroken run of entries. Whether that run is still live is decided above it,
/// in `current_streak`.
const RUN_LENGTH: &str = "
SELECT count(*) FROM entry
WHERE date >= (SELECT max(date) FROM entry
               WHERE date NOT IN (SELECT date(date,'+1 day') FROM entry))
";

/// The longest unbroken run ever recorded — artboard 02's `longest 96`.
///
/// Gaps and islands: consecutive dates minus their row number land on the same
/// day, so grouping by that day counts each run.
const LONGEST_RUN: &str = "
SELECT coalesce(max(length), 0) FROM (
    SELECT count(*) AS length FROM (
        SELECT date(date, '-' || row_number() OVER (ORDER BY date) || ' day') AS island
        FROM entry
    )
    GROUP BY island
)
";

/// Everything artboard 02's stat row shows, in one round trip.
#[derive(Debug, Clone, Serialize, PartialEq, Eq, Default)]
pub struct TodayStats {
    pub date: String,
    pub minutes: i64,
    pub floor_day: bool,
    pub current_streak: i64,
    pub longest_streak: i64,
    /// `floor met 118 / 140` — days that reached the floor, over days logged.
    pub floor_met: i64,
    pub days_logged: i64,
}

/// The counts beside each nav item (artboard 02's left nav).
///
/// `outputs` serves both `Outputs` and `The Wall` — they are the same figure,
/// which is why the artboard shows 27 twice.
#[derive(Debug, Clone, Serialize, PartialEq, Eq, Default)]
pub struct NavCounts {
    pub today_minutes: i64,
    pub monographs: i64,
    pub references: i64,
    pub outputs: i64,
    /// Phone lines not yet routed. The nav shows a badge when this is not zero.
    pub inbox_pending: i64,
}

fn count(connection: &Connection, sql: &str) -> Result<i64> {
    Ok(connection.query_row(sql, [], |row| row.get(0))?)
}

/// The streak as the interface reports it: 0 once the run has been broken.
///
/// A run counts as live while it reaches today or yesterday — an unlogged
/// morning is not a broken streak. Artboard 08 state 5 is the specification for
/// the broken case. This mirrors `ledger.entries.current_streak`; the two are
/// kept identical deliberately and both are tested against the same cases.
fn current_streak(connection: &Connection) -> Result<i64> {
    let last: Option<String> =
        connection.query_row("SELECT max(date) FROM entry", [], |row| row.get(0))?;

    let Some(last) = last else { return Ok(0) };

    let yesterday: String =
        connection.query_row("SELECT date('now','-1 day')", [], |row| row.get(0))?;

    if last < yesterday {
        return Ok(0);
    }

    count(connection, RUN_LENGTH)
}

pub fn today_stats(path: &Path) -> Result<TodayStats> {
    let connection = open_checked(path)?;

    let date: String = connection.query_row("SELECT date('now')", [], |row| row.get(0))?;

    let today: Option<(i64, i64)> = connection
        .query_row(
            "SELECT minutes, floor_day FROM entry WHERE date = ?1",
            [&date],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .ok();

    let (minutes, floor_day) = today.unwrap_or((0, 0));

    Ok(TodayStats {
        date,
        minutes,
        floor_day: floor_day != 0,
        current_streak: current_streak(&connection)?,
        longest_streak: count(&connection, LONGEST_RUN)?,
        floor_met: count(
            &connection,
            &format!("SELECT count(*) FROM entry WHERE minutes >= {FLOOR_MINUTES}"),
        )?,
        days_logged: count(&connection, "SELECT count(*) FROM entry")?,
    })
}

/// One row of artboard 03's corpus table.
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct CorpusRow {
    pub id: i64,
    pub accepted_name: Option<String>,
    pub authority: Option<String>,
    pub family: Option<String>,
    pub part: Option<String>,
    pub status: String,
    pub indications: i64,
    /// The maximum evidence across this record's indications, or None if it
    /// has none. A monograph's headline evidence is the maximum (BUILD.md §4).
    pub evidence: Option<String>,
    pub first_written: String,
    /// Bound to at least one output. The `never published on` flag is the
    /// absence of this on a record that is `sourced` or `reviewed`.
    pub published: bool,
    /// Has a benefit-sharing record. Its absence is a corpus filter flag, and
    /// benefit-sharing is not optional chrome (DESIGN.md §8).
    pub benefit_sharing: bool,
}

/// The corpus screen: its rows, its header counts and its footer counts.
#[derive(Debug, Clone, Serialize, PartialEq, Eq, Default)]
pub struct Corpus {
    pub rows: Vec<CorpusRow>,
    pub total: i64,
    pub indications: i64,
    /// The gap query, permanently visible in the footer (BUILD.md §4).
    pub never_published_on: i64,
}

/// Rank the evidence enum in SQL, so `max` means what the design means.
const EVIDENCE_RANK: &str = "CASE evidence
    WHEN 'traditional_only' THEN 1
    WHEN 'in_vitro' THEN 2
    WHEN 'in_vivo' THEN 3
    WHEN 'human_uncontrolled' THEN 4
    WHEN 'rct' THEN 5
    WHEN 'meta_analysis' THEN 6
END";

pub fn corpus(path: &Path) -> Result<Corpus> {
    let connection = open_checked(path)?;

    let sql = format!(
        "SELECT m.id, m.accepted_name, m.authority, m.family, m.part, m.status,
                (SELECT count(*) FROM indication i WHERE i.monograph_id = m.id),
                (SELECT i.evidence FROM indication i WHERE i.monograph_id = m.id
                   ORDER BY {EVIDENCE_RANK} DESC LIMIT 1),
                m.first_written,
                EXISTS (SELECT 1 FROM output_monograph om WHERE om.monograph_id = m.id),
                EXISTS (SELECT 1 FROM benefit_sharing b WHERE b.monograph_id = m.id)
         FROM monograph m
         ORDER BY m.first_written, m.id"
    );

    let mut statement = connection.prepare(&sql)?;
    let rows = statement.query_map([], |row| {
        Ok(CorpusRow {
            id: row.get(0)?,
            accepted_name: row.get(1)?,
            authority: row.get(2)?,
            family: row.get(3)?,
            part: row.get(4)?,
            status: row.get(5)?,
            indications: row.get(6)?,
            evidence: row.get(7)?,
            first_written: row.get(8)?,
            published: row.get::<_, i64>(9)? != 0,
            benefit_sharing: row.get::<_, i64>(10)? != 0,
        })
    })?;

    let rows: Vec<CorpusRow> = rows.collect::<std::result::Result<_, _>>()?;

    Ok(Corpus {
        total: rows.len() as i64,
        rows,
        indications: count(&connection, "SELECT count(*) FROM indication")?,
        // BUILD.md §4's gap query, verbatim.
        never_published_on: count(
            &connection,
            "SELECT count(*) FROM (
                 SELECT m.id FROM monograph m
                 LEFT JOIN output_monograph om ON om.monograph_id = m.id
                 WHERE om.output_id IS NULL AND m.status IN ('sourced','reviewed')
             )",
        )?,
    })
}

/// What `ledger ref --json` said, reduced to what the deposit row shows.
///
/// The sidecar owns Crossref (BUILD.md §3): Rust has no HTTP client and never
/// grows one. This end only reads the answer.
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct FetchResult {
    pub ok: bool,
    pub reference_id: Option<i64>,
    pub title: Option<String>,
    /// The line the deposit row's meta slot shows. Never empty.
    pub message: String,
}

/// Read the sidecar's `--json` answer.
///
/// Three shapes, from `ledger/commands/ref.py`: a bare `error` (a DOI that is
/// not a DOI, or one Crossref has never heard of), a row plus a `note` (the
/// network failed and the DOI was kept), or a plain row (resolved).
pub fn parse_fetch(stdout: &str, elapsed_ms: u128) -> FetchResult {
    let Ok(value) = serde_json::from_str::<serde_json::Value>(stdout.trim()) else {
        let line = stdout.trim().lines().next().unwrap_or("").trim();
        return FetchResult {
            ok: false,
            reference_id: None,
            title: None,
            message: if line.is_empty() {
                "the sidecar said nothing".into()
            } else {
                line.to_string()
            },
        };
    };

    let reference_id = value.get("id").and_then(serde_json::Value::as_i64);
    let title = value
        .get("title")
        .and_then(serde_json::Value::as_str)
        .map(str::to_string);

    if let Some(error) = value.get("error").and_then(serde_json::Value::as_str) {
        return FetchResult {
            ok: false,
            reference_id,
            title: None,
            message: error.to_string(),
        };
    }

    // A `note` means the row was kept but not resolved — the offline path.
    if let Some(note) = value.get("note").and_then(serde_json::Value::as_str) {
        return FetchResult {
            ok: false,
            reference_id,
            title,
            message: note.to_string(),
        };
    }

    FetchResult {
        ok: true,
        reference_id,
        title,
        // Artboard 09's `resolved in 240 ms`.
        message: format!("resolved in {elapsed_ms} ms"),
    }
}

/// One row of artboard 02's `last fourteen days` table.
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct DayRow {
    pub date: String,
    /// `MON` — the artboard sets it uppercase.
    pub dow: String,
    pub minutes: i64,
    /// The day has an entry. A day deposited against but not worked is logged
    /// at 0 minutes, which is not the same as a day that never happened.
    pub logged: bool,
    /// The day was declared a floor day. See STATE.md, sessions 03 and 19.
    pub floor_day: bool,
    pub is_today: bool,
    /// Binomials whose record was first written this day. Rendered italic.
    pub monographs: Vec<String>,
    pub references: i64,
    /// Output kinds deposited this day.
    pub outputs: Vec<String>,
}

/// The table and its header: `1,025 min · 73 avg · 4 floor days`.
#[derive(Debug, Clone, Serialize, PartialEq, Eq, Default)]
pub struct DayLog {
    pub days: Vec<DayRow>,
    pub total_minutes: i64,
    pub average: i64,
    pub floor_days: i64,
}

/// The last `span` days, newest first, whether or not each was logged.
///
/// An unlogged day is a real row at 0 minutes rather than a gap — fourteen
/// rows always, so the shape of a fortnight is visible.
pub fn day_log(path: &Path, span: i64) -> Result<DayLog> {
    let connection = open_checked(path)?;

    let mut statement = connection.prepare(
        "WITH RECURSIVE span(offset) AS (
             SELECT 0 UNION ALL SELECT offset + 1 FROM span WHERE offset + 1 < ?1
         ),
         day(date) AS (SELECT date('now', '-' || offset || ' day') FROM span)
         SELECT
             day.date,
             upper(strftime('%w', day.date)) AS weekday,
             coalesce(e.minutes, 0),
             e.id IS NOT NULL,
             coalesce(e.floor_day, 0),
             (SELECT count(*) FROM reference r WHERE date(r.added_at) = day.date),
             (SELECT group_concat(m.accepted_name, char(31))
                FROM monograph m WHERE m.first_written = day.date),
             (SELECT group_concat(o.kind, char(31))
                FROM output o WHERE o.date = day.date)
         FROM day
         LEFT JOIN entry e ON e.date = day.date
         ORDER BY day.date DESC",
    )?;

    let today: String = connection.query_row("SELECT date('now')", [], |row| row.get(0))?;

    let rows = statement.query_map([span], |row| {
        let date: String = row.get(0)?;
        let weekday: String = row.get(1)?;
        let monographs: Option<String> = row.get(6)?;
        let outputs: Option<String> = row.get(7)?;

        Ok(DayRow {
            dow: day_abbreviation(&weekday),
            is_today: date == today,
            date,
            minutes: row.get(2)?,
            logged: row.get::<_, i64>(3)? != 0,
            floor_day: row.get::<_, i64>(4)? != 0,
            references: row.get(5)?,
            monographs: split_list(monographs),
            outputs: split_list(outputs),
        })
    })?;

    let days: Vec<DayRow> = rows.collect::<std::result::Result<_, _>>()?;

    let total_minutes: i64 = days.iter().map(|day| day.minutes).sum();
    let floor_days = days.iter().filter(|day| day.floor_day).count() as i64;
    let average = if days.is_empty() {
        0
    } else {
        total_minutes / days.len() as i64
    };

    Ok(DayLog {
        days,
        total_minutes,
        average,
        floor_days,
    })
}

/// `group_concat` joined on unit separator — a character no field can contain.
fn split_list(joined: Option<String>) -> Vec<String> {
    joined
        .filter(|value| !value.is_empty())
        .map(|value| value.split('\u{1f}').map(str::to_string).collect())
        .unwrap_or_default()
}

/// SQLite's `%w` is 0 = Sunday.
fn day_abbreviation(weekday: &str) -> String {
    match weekday {
        "0" => "SUN",
        "1" => "MON",
        "2" => "TUE",
        "3" => "WED",
        "4" => "THU",
        "5" => "FRI",
        "6" => "SAT",
        _ => "",
    }
    .to_string()
}

/// The note as the day holds it, plus what the autosave footer reports.
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct SavedNote {
    pub entry_id: i64,
    pub note: String,
    /// `autosaved 14:22` — local time, as the artboard sets it.
    pub saved_at: String,
}

/// Write today's note. Opens the day if it is not open yet.
///
/// The same path serves the 2-second autosave and the explicit `Save entry`
/// button: one write, so the two can never disagree about what is on disk.
pub fn save_note(path: &Path, note: &str) -> Result<SavedNote> {
    let connection = open_checked(path)?;

    connection.execute(
        "INSERT INTO entry (date, note) VALUES (date('now'), ?1)
         ON CONFLICT(date) DO UPDATE SET note = ?1, updated_at = datetime('now')",
        [note],
    )?;

    let (entry_id, saved_at) = connection.query_row(
        "SELECT id, strftime('%H:%M', updated_at, 'localtime') FROM entry WHERE date = date('now')",
        [],
        |row| Ok((row.get(0)?, row.get(1)?)),
    )?;

    Ok(SavedNote {
        entry_id,
        note: note.to_string(),
        saved_at,
    })
}

pub fn note_for_today(path: &Path) -> Result<SavedNote> {
    let connection = open_checked(path)?;

    let found: Option<(i64, String, String)> = connection
        .query_row(
            "SELECT id, note, strftime('%H:%M', updated_at, 'localtime')
             FROM entry WHERE date = date('now')",
            [],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )
        .ok();

    Ok(match found {
        Some((entry_id, note, saved_at)) => SavedNote {
            entry_id,
            note,
            saved_at,
        },
        None => SavedNote {
            entry_id: 0,
            note: String::new(),
            saved_at: String::new(),
        },
    })
}

/// The id of today's entry, opening the day if it is not open yet.
fn today_entry(connection: &Connection) -> Result<i64> {
    connection.execute(
        "INSERT OR IGNORE INTO entry (date) VALUES (date('now'))",
        [],
    )?;
    Ok(
        connection.query_row("SELECT id FROM entry WHERE date = date('now')", [], |row| {
            row.get(0)
        })?,
    )
}

/// A monograph skeleton opened from the deposit row.
///
/// The typed name goes straight into `accepted_name` with the identifiers left
/// NULL — that NULL is what puts the record in the review queue, where
/// `ledger resolve` picks it up. Nothing here guesses at a name.
pub fn open_monograph(path: &Path, name: &str) -> Result<i64> {
    let name = name.trim();
    if name.is_empty() {
        return Err(Error::Refused("a monograph needs a name".into()));
    }

    let connection = open_checked(path)?;

    if let Ok(existing) = connection.query_row(
        "SELECT id FROM monograph WHERE accepted_name = ?1",
        [name],
        |row| row.get(0),
    ) {
        return Ok(existing);
    }

    connection.execute("INSERT INTO monograph (accepted_name) VALUES (?1)", [name])?;
    Ok(connection.last_insert_rowid())
}

/// An output recorded against today's entry.
pub fn add_output(path: &Path, kind: &str, title: &str) -> Result<i64> {
    let title = title.trim();
    if title.is_empty() {
        return Err(Error::Refused("an output needs a title".into()));
    }

    let connection = open_checked(path)?;
    let entry_id = today_entry(&connection)?;

    // The CHECK constraint on `output.kind` is what actually refuses an
    // invented kind; this turns that into a sentence rather than a raw error.
    if !["paper", "talk", "long-form", "release", "note"].contains(&kind) {
        return Err(Error::Refused(format!("{kind} is not an output kind")));
    }

    connection.execute(
        "INSERT INTO output (kind, title, date, entry_id)
         VALUES (?1, ?2, date('now'), ?3)",
        rusqlite::params![kind, title, entry_id],
    )?;

    Ok(connection.last_insert_rowid())
}

/// Mark today a floor day, or unmark it. Opens the day if it is not open yet —
/// saying "yes, today was a floor day" is itself a record of the day.
pub fn set_floor_day(path: &Path, floor_day: bool) -> Result<TodayStats> {
    {
        let connection = open_checked(path)?;
        connection.execute(
            "INSERT INTO entry (date, floor_day) VALUES (date('now'), ?1)
             ON CONFLICT(date) DO UPDATE SET floor_day = ?1, updated_at = datetime('now')",
            [i64::from(floor_day)],
        )?;
    }

    today_stats(path)
}

pub fn nav_counts(path: &Path) -> Result<NavCounts> {
    let connection = open_checked(path)?;

    Ok(NavCounts {
        today_minutes: count(
            &connection,
            "SELECT coalesce((SELECT minutes FROM entry WHERE date = date('now')), 0)",
        )?,
        monographs: count(&connection, "SELECT count(*) FROM monograph")?,
        references: count(&connection, "SELECT count(*) FROM reference")?,
        outputs: count(&connection, "SELECT count(*) FROM output")?,
        inbox_pending: count(
            &connection,
            "SELECT count(*) FROM inbox_line WHERE consumed_at IS NULL",
        )?,
    })
}
