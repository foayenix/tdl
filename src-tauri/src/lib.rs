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

/// What the footer shows: the path, the size on disk, and the schema.
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct Status {
    pub path: String,
    pub bytes: u64,
    pub schema_version: i64,
}

pub fn status(path: &Path) -> Result<Status> {
    let connection = open_checked(path)?;
    let bytes = std::fs::metadata(path).map(|meta| meta.len()).unwrap_or(0);

    Ok(Status {
        path: path.display().to_string(),
        bytes,
        schema_version: user_version(&connection)?,
    })
}
