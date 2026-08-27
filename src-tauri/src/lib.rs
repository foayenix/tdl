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

/// The record header and its two strips (artboard 05).
///
/// This is the screen where the work actually happens, and §1 says it does not
/// move: a corpus table with no detail view is a list of names.
// f64 has no Eq — gbif_confidence is a measurement, not an identity.
#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct Record {
    pub id: i64,
    pub accepted_name: Option<String>,
    pub authority: Option<String>,
    pub family: Option<String>,
    pub part: Option<String>,
    pub habitat_note: Option<String>,
    pub wfo_id: Option<String>,
    pub gbif_key: Option<i64>,
    pub gbif_confidence: Option<f64>,
    pub status: String,
    pub summary: Option<String>,
    pub summary_rewritten_at: Option<String>,
    pub preparation: Option<String>,
    pub first_written: String,
    pub last_touched: String,

    // The summary strip: `7 indications · 19 references bound ·
    // strongest evidence E5 RCT · 3 rows unsourced`.
    pub indications: i64,
    pub references_bound: i64,
    pub strongest_evidence: Option<String>,
    pub unsourced: i64,
}

pub fn record(path: &Path, id: i64) -> Result<Record> {
    let connection = open_checked(path)?;

    let sql = format!(
        "SELECT m.id, m.accepted_name, m.authority, m.family, m.part, m.habitat_note,
                m.wfo_id, m.gbif_key, m.gbif_confidence, m.status, m.summary,
                m.summary_rewritten_at, m.preparation, m.first_written,
                strftime('%Y-%m-%d %H:%M', m.last_touched, 'localtime'),
                (SELECT count(*) FROM indication i WHERE i.monograph_id = m.id),
                (SELECT count(DISTINCT mr.reference_id) FROM monograph_reference mr
                   WHERE mr.monograph_id = m.id),
                (SELECT i.evidence FROM indication i WHERE i.monograph_id = m.id
                   ORDER BY {EVIDENCE_RANK} DESC LIMIT 1),
                (SELECT count(*) FROM unsourced_claim u WHERE u.monograph_id = m.id)
         FROM monograph m WHERE m.id = ?1"
    );

    connection
        .query_row(&sql, [id], |row| {
            Ok(Record {
                id: row.get(0)?,
                accepted_name: row.get(1)?,
                authority: row.get(2)?,
                family: row.get(3)?,
                part: row.get(4)?,
                habitat_note: row.get(5)?,
                wfo_id: row.get(6)?,
                gbif_key: row.get(7)?,
                gbif_confidence: row.get(8)?,
                status: row.get(9)?,
                summary: row.get(10)?,
                summary_rewritten_at: row.get(11)?,
                preparation: row.get(12)?,
                first_written: row.get(13)?,
                last_touched: row.get(14)?,
                indications: row.get(15)?,
                references_bound: row.get(16)?,
                strongest_evidence: row.get(17)?,
                unsourced: row.get(18)?,
            })
        })
        .map_err(|error| match error {
            rusqlite::Error::QueryReturnedNoRows => Error::Refused(format!("no monograph {id}")),
            other => Error::Sqlite(other),
        })
}

/// One GBIF candidate, as artboard 08 state 4 lists them.
#[derive(Debug, Clone, Serialize, PartialEq, Default)]
pub struct Candidate {
    pub name: Option<String>,
    pub gbif_key: Option<i64>,
    pub confidence: f64,
}

/// What `ledger resolve --json` said about one record.
#[derive(Debug, Clone, Serialize, PartialEq, Default)]
pub struct Resolution {
    pub accepted: bool,
    pub reason: String,
    pub confidence: Option<f64>,
    pub name: Option<String>,
    pub candidates: Vec<Candidate>,
}

/// Read the sidecar's answer. The CLI prints an array, one entry per record.
pub fn parse_resolution(stdout: &str) -> Resolution {
    let Ok(value) = serde_json::from_str::<serde_json::Value>(stdout.trim()) else {
        return Resolution {
            reason: stdout
                .trim()
                .lines()
                .next()
                .unwrap_or("the sidecar said nothing")
                .to_string(),
            ..Resolution::default()
        };
    };

    let first = value.get(0).unwrap_or(&value);

    let candidates = first
        .get("candidates")
        .and_then(serde_json::Value::as_array)
        .map(|items| {
            items
                .iter()
                .map(|item| Candidate {
                    name: item
                        .get("name")
                        .and_then(serde_json::Value::as_str)
                        .map(str::to_string),
                    gbif_key: item.get("gbif_key").and_then(serde_json::Value::as_i64),
                    confidence: item
                        .get("confidence")
                        .and_then(serde_json::Value::as_f64)
                        .unwrap_or(0.0),
                })
                .collect()
        })
        .unwrap_or_default();

    Resolution {
        accepted: first
            .get("accepted")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(false),
        reason: first
            .get("reason")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("no answer")
            .to_string(),
        confidence: first.get("confidence").and_then(serde_json::Value::as_f64),
        name: first
            .get("name")
            .and_then(serde_json::Value::as_str)
            .map(str::to_string),
        candidates,
    }
}

/// `Enter name by hand` — artboard 08 state 4's second action.
///
/// A person deciding is not the machine guessing, which is what invariant 2
/// guards against. The identifiers stay NULL, so the record stays in the queue
/// until something confirms it.
pub fn set_name_by_hand(path: &Path, monograph_id: i64, name: &str) -> Result<Record> {
    let name = name.trim();
    if name.is_empty() {
        return Err(Error::Refused("a monograph needs a name".into()));
    }

    let connection = open_checked(path)?;
    connection.execute(
        "UPDATE monograph SET accepted_name = ?2, last_touched = datetime('now')
         WHERE id = ?1",
        rusqlite::params![monograph_id, name],
    )?;

    record(path, monograph_id)
}

/// Artboard 08 state 5 — a streak that has been broken.
///
/// No guilt copy, no flame, no offer to restore it. The days are listed
/// plainly and counting resumes at 1 (BUILD.md §8).
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct BrokenStreak {
    /// The last day of the run that ended.
    pub ended_on: String,
    /// How long that run was.
    pub length: i64,
    /// The days since, in order, none of which has an entry.
    pub missed: Vec<String>,
}

/// The break, or None when the streak is live or there is nothing to break.
pub fn broken_streak(path: &Path) -> Result<Option<BrokenStreak>> {
    let connection = open_checked(path)?;

    if current_streak(&connection)? > 0 {
        return Ok(None);
    }

    let last: Option<String> =
        connection.query_row("SELECT max(date) FROM entry", [], |row| row.get(0))?;
    let Some(ended_on) = last else {
        return Ok(None);
    };

    let length = count(&connection, RUN_LENGTH)?;

    let mut statement = connection.prepare(
        "WITH RECURSIVE gap(day) AS (
             SELECT date(?1, '+1 day')
             UNION ALL
             SELECT date(day, '+1 day') FROM gap WHERE day < date('now')
         )
         SELECT day FROM gap
         WHERE day NOT IN (SELECT date FROM entry)
         ORDER BY day",
    )?;

    let rows = statement.query_map([&ended_on], |row| row.get::<_, String>(0))?;
    let missed: Vec<String> = rows.collect::<std::result::Result<_, _>>()?;

    Ok(Some(BrokenStreak {
        ended_on,
        length,
        missed,
    }))
}

/// Artboard 08 state 4 — `queue 3 of 7`.
///
/// The queue is `status = 'skeleton' AND gbif_key IS NULL`, ordered by
/// `first_written`; there is no queue table (session 09).
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct QueuePosition {
    pub position: i64,
    pub total: i64,
}

pub fn queue_position(path: &Path, monograph_id: i64) -> Result<Option<QueuePosition>> {
    let connection = open_checked(path)?;

    let mut statement = connection.prepare(
        "SELECT id FROM monograph
         WHERE status = 'skeleton' AND gbif_key IS NULL
         ORDER BY first_written, id",
    )?;

    let rows = statement.query_map([], |row| row.get::<_, i64>(0))?;
    let queue: Vec<i64> = rows.collect::<std::result::Result<_, _>>()?;

    Ok(queue
        .iter()
        .position(|id| *id == monograph_id)
        .map(|index| QueuePosition {
            position: index as i64 + 1,
            total: queue.len() as i64,
        }))
}

/// The next skeleton waiting to be written — artboard 08 state 5's
/// `Open next skeleton`.
pub fn next_skeleton(path: &Path) -> Result<Option<i64>> {
    let connection = open_checked(path)?;

    Ok(connection
        .query_row(
            "SELECT id FROM monograph WHERE status = 'skeleton'
             ORDER BY first_written, id LIMIT 1",
            [],
            |row| row.get(0),
        )
        .ok())
}

/// A reference bound to this record, numbered **within the record**.
///
/// Artboard 05 labels them `R1`–`Rn` and the summary cites `sources R1, R2,
/// R6`, so the number is a position in this record's list, not the library's
/// row id. A record's sixth reference is R6 whether the library holds twelve
/// or twelve hundred.
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct BoundReference {
    pub position: i64,
    pub reference_id: i64,
    pub title: String,
    pub authors: Option<String>,
    pub journal: Option<String>,
    pub year: Option<i64>,
    pub doi: Option<String>,
    pub read_state: String,
    pub added_at: String,
    /// Which sections of the record cite it.
    pub sections: Vec<String>,
}

pub fn record_references(path: &Path, monograph_id: i64) -> Result<Vec<BoundReference>> {
    let connection = open_checked(path)?;

    let mut statement = connection.prepare(
        "SELECT r.id, r.title, r.authors, r.journal, r.year, r.doi, r.read_state, r.added_at,
                group_concat(mr.section, char(31))
         FROM reference r
         JOIN monograph_reference mr ON mr.reference_id = r.id
         WHERE mr.monograph_id = ?1
         GROUP BY r.id
         ORDER BY min(mr.bound_at), r.id",
    )?;

    let rows = statement.query_map([monograph_id], |row| {
        let sections: Option<String> = row.get(8)?;
        Ok(BoundReference {
            position: 0,
            reference_id: row.get(0)?,
            title: row.get(1)?,
            authors: row.get(2)?,
            journal: row.get(3)?,
            year: row.get(4)?,
            doi: row.get(5)?,
            read_state: row.get(6)?,
            added_at: row.get(7)?,
            sections: split_list(sections),
        })
    })?;

    let mut bound: Vec<BoundReference> = rows.collect::<std::result::Result<_, _>>()?;
    for (index, reference) in bound.iter_mut().enumerate() {
        reference.position = index as i64 + 1;
    }

    Ok(bound)
}

/// `cited by your outputs` — what this plant has appeared in.
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct CitingOutput {
    pub id: i64,
    pub kind: String,
    pub title: String,
    pub venue: Option<String>,
    pub date: String,
}

pub fn cited_by_outputs(path: &Path, monograph_id: i64) -> Result<Vec<CitingOutput>> {
    let connection = open_checked(path)?;

    let mut statement = connection.prepare(
        "SELECT o.id, o.kind, o.title, o.venue, o.date
         FROM output o
         JOIN output_monograph om ON om.output_id = o.id
         WHERE om.monograph_id = ?1
         ORDER BY o.date DESC, o.id DESC",
    )?;

    let rows = statement.query_map([monograph_id], |row| {
        Ok(CitingOutput {
            id: row.get(0)?,
            kind: row.get(1)?,
            title: row.get(2)?,
            venue: row.get(3)?,
            date: row.get(4)?,
        })
    })?;

    Ok(rows.collect::<std::result::Result<_, _>>()?)
}

/// `3 references queued, unread →` and `oldest queued 2026-07-02`.
#[derive(Debug, Clone, Serialize, PartialEq, Eq, Default)]
pub struct QueuedReading {
    pub count: i64,
    pub oldest: Option<String>,
}

pub fn queued_reading(path: &Path, monograph_id: i64) -> Result<QueuedReading> {
    let connection = open_checked(path)?;

    connection
        .query_row(
            // DISTINCT: a reference cited in two sections is bound twice and
            // would otherwise be counted twice.
            "SELECT count(DISTINCT r.id), min(date(r.added_at))
             FROM reference r
             JOIN monograph_reference mr ON mr.reference_id = r.id
             WHERE mr.monograph_id = ?1 AND r.read_state = 'queued'",
            [monograph_id],
            |row| {
                Ok(QueuedReading {
                    count: row.get(0)?,
                    oldest: row.get(1)?,
                })
            },
        )
        .map_err(Error::Sqlite)
}

/// Per-section unsourced counts — the rail shows them in `secondary`.
pub fn unsourced_by_section(path: &Path, monograph_id: i64) -> Result<Vec<(String, i64)>> {
    let connection = open_checked(path)?;

    let mut statement = connection.prepare(
        "SELECT claim_table, count(*) FROM unsourced_claim
         WHERE monograph_id = ?1 GROUP BY claim_table",
    )?;

    let rows = statement.query_map([monograph_id], |row| Ok((row.get(0)?, row.get(1)?)))?;
    Ok(rows.collect::<std::result::Result<_, _>>()?)
}

/// The benefit-sharing record. One row per monograph, and not optional chrome:
/// it records consent, named attribution and the agreement under which
/// vernacular and preparation knowledge was collected (DESIGN.md §8).
#[derive(Debug, Clone, Serialize, PartialEq, Eq, Default)]
pub struct BenefitSharing {
    pub narrative: Option<String>,
    pub agreement_ref: Option<String>,
    pub expires: Option<String>,
    pub consent_recorded_at: Option<String>,
    /// False when the record has no benefit-sharing row at all — which is a
    /// corpus filter flag, so it is a fact worth carrying rather than inferring.
    pub present: bool,
}

pub fn benefit_sharing(path: &Path, monograph_id: i64) -> Result<BenefitSharing> {
    let connection = open_checked(path)?;

    let found = connection
        .query_row(
            "SELECT narrative, agreement_ref, expires, consent_recorded_at
             FROM benefit_sharing WHERE monograph_id = ?1",
            [monograph_id],
            |row| {
                Ok(BenefitSharing {
                    narrative: row.get(0)?,
                    agreement_ref: row.get(1)?,
                    expires: row.get(2)?,
                    consent_recorded_at: row.get(3)?,
                    present: true,
                })
            },
        )
        .ok();

    Ok(found.unwrap_or_default())
}

pub fn save_benefit_sharing(
    path: &Path,
    monograph_id: i64,
    narrative: Option<String>,
    agreement_ref: Option<String>,
    expires: Option<String>,
) -> Result<BenefitSharing> {
    let connection = open_checked(path)?;

    connection.execute(
        "INSERT INTO benefit_sharing (monograph_id, narrative, agreement_ref, expires)
         VALUES (?1, ?2, ?3, ?4)
         ON CONFLICT(monograph_id) DO UPDATE SET
             narrative = ?2, agreement_ref = ?3, expires = ?4",
        rusqlite::params![
            monograph_id,
            blank_to_null(narrative),
            blank_to_null(agreement_ref),
            blank_to_null(expires),
        ],
    )?;

    touch(&connection, monograph_id)?;
    benefit_sharing(path, monograph_id)
}

fn blank_to_null(value: Option<String>) -> Option<String> {
    value
        .map(|text| text.trim().to_string())
        .filter(|text| !text.is_empty())
}

fn touch(connection: &Connection, monograph_id: i64) -> Result<()> {
    connection.execute(
        "UPDATE monograph SET last_touched = datetime('now') WHERE id = ?1",
        [monograph_id],
    )?;
    Ok(())
}

/// Write one of the record's prose fields.
///
/// Rewriting the summary stamps `summary_rewritten_at`; writing the same text
/// again does not, so the date means what it says.
pub fn save_prose(path: &Path, monograph_id: i64, field: &str, text: &str) -> Result<Record> {
    if !matches!(field, "summary" | "preparation") {
        return Err(Error::Refused(format!("{field} is not a prose field")));
    }

    let connection = open_checked(path)?;
    let value = blank_to_null(Some(text.to_string()));

    if field == "summary" {
        let before: Option<String> = connection.query_row(
            "SELECT summary FROM monograph WHERE id = ?1",
            [monograph_id],
            |row| row.get(0),
        )?;

        if before != value {
            connection.execute(
                "UPDATE monograph SET summary = ?2, summary_rewritten_at = date('now'),
                 last_touched = datetime('now') WHERE id = ?1",
                rusqlite::params![monograph_id, value],
            )?;
            return record(path, monograph_id);
        }
    }

    connection.execute(
        &format!(
            "UPDATE monograph SET \"{field}\" = ?2, last_touched = datetime('now')
             WHERE id = ?1"
        ),
        rusqlite::params![monograph_id, value],
    )?;

    record(path, monograph_id)
}

/// The reference ids cited in one section — artboard 05's `sources R1, R2, R6`.
pub fn section_sources(path: &Path, monograph_id: i64, section: &str) -> Result<Vec<i64>> {
    let connection = open_checked(path)?;

    let mut statement = connection.prepare(
        "SELECT DISTINCT reference_id FROM monograph_reference
         WHERE monograph_id = ?1 AND section = ?2 ORDER BY reference_id",
    )?;

    let rows = statement.query_map(rusqlite::params![monograph_id, section], |row| row.get(0))?;
    Ok(rows.collect::<std::result::Result<_, _>>()?)
}

/// A claim row as the record shows it. Every one carries a source, and a row
/// without one is the rule the whole screen is built around (DESIGN.md §6).
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct Claim {
    pub id: i64,
    /// The claim's own columns, in the order the record shows them.
    pub cells: Vec<Option<String>>,
    pub source_reference_id: Option<i64>,
    pub source_note: Option<String>,
}

impl Claim {
    /// True when this row reads `⚠ source needed`.
    pub fn is_unsourced(&self) -> bool {
        self.source_reference_id.is_none()
            && self
                .source_note
                .as_deref()
                .map(str::trim)
                .unwrap_or("")
                .is_empty()
    }
}

/// The columns each claim table contributes, in record order. This is the one
/// place that mapping lives; `ledger.claims.CLAIM_TABLES` is its twin.
pub fn claim_columns(table: &str) -> Option<&'static [&'static str]> {
    match table {
        "vernacular" => Some(&["name", "language", "region"]),
        "indication" => Some(&["condition", "tradition", "region", "evidence"]),
        "constituent" => Some(&["compound", "class", "inchikey"]),
        "safety" => Some(&["kind", "finding", "severity"]),
        _ => None,
    }
}

pub fn claims(path: &Path, monograph_id: i64, table: &str) -> Result<Vec<Claim>> {
    let Some(columns) = claim_columns(table) else {
        return Err(Error::Refused(format!("{table} is not a claim table")));
    };

    let connection = open_checked(path)?;

    let selected = columns
        .iter()
        .map(|column| format!("\"{column}\""))
        .collect::<Vec<_>>()
        .join(", ");

    let sql = format!(
        "SELECT id, {selected}, source_reference_id, source_note
         FROM \"{table}\" WHERE monograph_id = ?1 ORDER BY id"
    );

    let mut statement = connection.prepare(&sql)?;
    let rows = statement.query_map([monograph_id], |row| {
        let mut cells = Vec::with_capacity(columns.len());
        for index in 0..columns.len() {
            cells.push(row.get::<_, Option<String>>(index + 1)?);
        }
        Ok(Claim {
            id: row.get(0)?,
            source_reference_id: row.get(columns.len() + 1)?,
            source_note: row.get(columns.len() + 2)?,
            cells,
        })
    })?;

    Ok(rows.collect::<std::result::Result<_, _>>()?)
}

/// Add one claim row from the record's inline `+ add`.
///
/// `values` is positional, matching `claim_columns`. A blank source is allowed
/// and is exactly what makes the row render as unsourced — the database, not
/// this function, is what stops such a record reaching `reviewed`.
pub fn add_claim(
    path: &Path,
    monograph_id: i64,
    table: &str,
    values: Vec<String>,
    source_note: Option<String>,
) -> Result<i64> {
    let Some(columns) = claim_columns(table) else {
        return Err(Error::Refused(format!("{table} is not a claim table")));
    };

    if values.len() != columns.len() {
        return Err(Error::Refused(format!(
            "{table} takes {} values, got {}",
            columns.len(),
            values.len()
        )));
    }

    // The first column is the claim itself; a row without it says nothing.
    if values[0].trim().is_empty() {
        return Err(Error::Refused(format!(
            "a {table} row needs a {}",
            columns[0]
        )));
    }

    let connection = open_checked(path)?;

    let names = columns
        .iter()
        .map(|column| format!("\"{column}\""))
        .collect::<Vec<_>>()
        .join(", ");
    let placeholders = (0..columns.len())
        .map(|index| format!("?{}", index + 2))
        .collect::<Vec<_>>()
        .join(", ");

    let sql = format!(
        "INSERT INTO \"{table}\" (monograph_id, {names}, source_note)
         VALUES (?1, {placeholders}, ?{})",
        columns.len() + 2
    );

    let mut parameters: Vec<Box<dyn rusqlite::ToSql>> = vec![Box::new(monograph_id)];
    for (index, value) in values.iter().enumerate() {
        let trimmed = value.trim();
        // An optional column left blank is NULL, not an empty string — the
        // difference matters to `coalesce` and to the unsourced view.
        if trimmed.is_empty() && index > 0 {
            parameters.push(Box::new(None::<String>));
        } else {
            parameters.push(Box::new(trimmed.to_string()));
        }
    }
    let note = source_note
        .map(|note| note.trim().to_string())
        .filter(|note| !note.is_empty());
    parameters.push(Box::new(note));

    let borrowed: Vec<&dyn rusqlite::ToSql> =
        parameters.iter().map(|value| value.as_ref()).collect();

    connection
        .execute(&sql, borrowed.as_slice())
        .map_err(|error| match error {
            rusqlite::Error::SqliteFailure(_, Some(ref message))
                if message.contains("unsourced row") =>
            {
                Error::Refused(
                    "a reviewed monograph cannot take an unsourced row — source it first".into(),
                )
            }
            other => Error::Sqlite(other),
        })?;

    Ok(connection.last_insert_rowid())
}

/// What a `find` searched and what it found.
// f64 has no Eq — the elapsed time is a measurement, not an identity.
#[derive(Debug, Clone, Serialize, PartialEq, Default)]
pub struct SearchResult {
    /// Records the query touched, by name or through a claim row.
    pub monograph_ids: Vec<i64>,
    /// Every hit, claim rows included — artboard 03's `6 hits`.
    pub hits: i64,
    pub monographs_searched: i64,
    pub references_searched: i64,
    pub outputs_searched: i64,
    pub milliseconds: f64,
}

/// Turn what someone typed into an FTS5 MATCH expression.
///
/// Every token is quoted, so a hyphen, the slash in a DOI or a literal `OR` is
/// searched for rather than parsed as syntax. Tokens are ANDed. This mirrors
/// `ledger.find.to_match`; both are tested against the same awkward inputs.
pub fn to_match(query: &str) -> Option<String> {
    let tokens: Vec<String> = query
        .split(|character: char| !character.is_alphanumeric())
        .filter(|token| !token.is_empty())
        .map(|token| format!("\"{token}\""))
        .collect();

    if tokens.is_empty() {
        None
    } else {
        Some(tokens.join(" AND "))
    }
}

pub fn search(path: &Path, query: &str) -> Result<SearchResult> {
    let connection = open_checked(path)?;

    let searched = SearchResult {
        monographs_searched: count(&connection, "SELECT count(*) FROM monograph")?,
        references_searched: count(&connection, "SELECT count(*) FROM reference")?,
        outputs_searched: count(&connection, "SELECT count(*) FROM output")?,
        ..SearchResult::default()
    };

    let Some(expression) = to_match(query) else {
        return Ok(searched);
    };

    let started = std::time::Instant::now();

    let mut statement = connection.prepare(
        "SELECT kind, row_id, monograph_id FROM search WHERE search MATCH ?1 ORDER BY rank",
    )?;

    let mut monograph_ids: Vec<i64> = Vec::new();
    let mut hits = 0i64;

    let rows = statement.query_map([&expression], |row| {
        let kind: String = row.get(0)?;
        let row_id: i64 = row.get(1)?;
        let monograph_id: Option<i64> = row.get(2)?;
        Ok((kind, row_id, monograph_id))
    })?;

    for row in rows {
        let (kind, row_id, monograph_id) = row?;
        hits += 1;

        // A monograph hit points at itself; a claim hit points at its plant.
        let touched = if kind == "monograph" {
            Some(row_id)
        } else {
            monograph_id
        };

        if let Some(id) = touched {
            if !monograph_ids.contains(&id) {
                monograph_ids.push(id);
            }
        }
    }

    Ok(SearchResult {
        monograph_ids,
        hits,
        milliseconds: started.elapsed().as_secs_f64() * 1000.0,
        ..searched
    })
}

/// The nearest accepted name to a query, and its edit distance.
///
/// Artboard 08 state 6 shows this beside a query that found nothing, so the
/// answer to "did I spell it wrong" is on screen rather than in your head.
pub fn nearest_name(path: &Path, query: &str) -> Result<Option<(String, usize)>> {
    let connection = open_checked(path)?;

    let mut statement = connection
        .prepare("SELECT accepted_name FROM monograph WHERE accepted_name IS NOT NULL")?;
    let names = statement.query_map([], |row| row.get::<_, String>(0))?;

    let query = query.to_lowercase();
    let mut best: Option<(String, usize)> = None;

    for name in names {
        let name = name?;
        let distance = edit_distance(&query, &name.to_lowercase());
        // Written out rather than `is_none_or`, which is newer than this
        // crate's declared MSRV.
        let closer = match &best {
            None => true,
            Some((_, shortest)) => distance < *shortest,
        };
        if closer {
            best = Some((name, distance));
        }
    }

    Ok(best)
}

/// Levenshtein, two rows at a time.
fn edit_distance(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();

    let mut previous: Vec<usize> = (0..=b.len()).collect();

    for (i, left) in a.iter().enumerate() {
        let mut current = vec![i + 1];
        for (j, right) in b.iter().enumerate() {
            current.push(
                (previous[j + 1] + 1)
                    .min(current[j] + 1)
                    .min(previous[j] + usize::from(left != right)),
            );
        }
        previous = current;
    }

    previous[b.len()]
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
