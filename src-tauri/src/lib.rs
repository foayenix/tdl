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
