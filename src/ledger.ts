// The only way the frontend reaches the database is through a Rust command.
// It holds no shell permission and opens no connection of its own.
import { invoke } from "@tauri-apps/api/core";

export type Status = {
  path: string;
  bytes: number;
  schema_version: number;
  last_write: number | null;
};

export type NavCounts = {
  today_minutes: number;
  monographs: number;
  references: number;
  outputs: number;
  inbox_pending: number;
};

export async function status(): Promise<Status> {
  return invoke<Status>("ledger_status");
}

export type TodayStats = {
  date: string;
  minutes: number;
  logged: boolean;
  floor_day: boolean;
  current_streak: number;
  longest_streak: number;
  floor_met: number;
  days_logged: number;
};

export async function navCounts(): Promise<NavCounts> {
  return invoke<NavCounts>("ledger_nav_counts");
}

export async function todayStats(): Promise<TodayStats> {
  return invoke<TodayStats>("ledger_today");
}

export async function setFloorDay(floorDay: boolean): Promise<TodayStats> {
  return invoke<TodayStats>("ledger_set_floor_day", { floorDay });
}

export type SavedNote = {
  entry_id: number;
  note: string;
  saved_at: string;
};

export async function note(): Promise<SavedNote> {
  return invoke<SavedNote>("ledger_note");
}

export async function saveNote(text: string): Promise<SavedNote> {
  return invoke<SavedNote>("ledger_save_note", { note: text });
}

export async function openMonograph(name: string): Promise<number> {
  return invoke<number>("ledger_open_monograph", { name });
}

export async function addOutput(kind: string, title: string): Promise<number> {
  return invoke<number>("ledger_add_output", { kind, title });
}

export type DayRow = {
  date: string;
  dow: string;
  minutes: number;
  logged: boolean;
  floor_day: boolean;
  is_today: boolean;
  monographs: string[];
  references: number;
  outputs: string[];
};

export type DayLog = {
  days: DayRow[];
  total_minutes: number;
  average: number;
  floor_days: number;
};

export async function dayLog(): Promise<DayLog> {
  return invoke<DayLog>("ledger_day_log");
}

export type CorpusRow = {
  id: number;
  accepted_name: string | null;
  authority: string | null;
  family: string | null;
  part: string | null;
  status: string;
  indications: number;
  evidence: string | null;
  first_written: string;
  published: boolean;
  benefit_sharing: boolean;
};

export type Corpus = {
  rows: CorpusRow[];
  total: number;
  indications: number;
  never_published_on: number;
};

export async function corpus(): Promise<Corpus> {
  return invoke<Corpus>("ledger_corpus");
}

export type Record = {
  id: number;
  accepted_name: string | null;
  authority: string | null;
  family: string | null;
  part: string | null;
  habitat_note: string | null;
  wfo_id: string | null;
  gbif_key: number | null;
  gbif_confidence: number | null;
  status: string;
  summary: string | null;
  summary_rewritten_at: string | null;
  preparation: string | null;
  first_written: string;
  last_touched: string;
  indications: number;
  references_bound: number;
  strongest_evidence: string | null;
  unsourced: number;
};

export async function record(id: number): Promise<Record> {
  return invoke<Record>("ledger_record", { id });
}

export type Claim = {
  id: number;
  cells: (string | null)[];
  source_reference_id: number | null;
  source_note: string | null;
};

export async function claims(id: number, table: string): Promise<Claim[]> {
  return invoke<Claim[]>("ledger_claims", { id, table });
}

export async function addClaim(
  id: number,
  table: string,
  values: string[],
  sourceNote: string | null,
): Promise<number> {
  return invoke<number>("ledger_add_claim", { id, table, values, sourceNote });
}

export type SearchResult = {
  monograph_ids: number[];
  hits: number;
  monographs_searched: number;
  references_searched: number;
  outputs_searched: number;
  milliseconds: number;
};

export async function search(query: string): Promise<SearchResult> {
  return invoke<SearchResult>("ledger_search", { query });
}

export async function nearestName(query: string): Promise<[string, number] | null> {
  return invoke<[string, number] | null>("ledger_nearest_name", { query });
}

export type FetchResult = {
  ok: boolean;
  reference_id: number | null;
  title: string | null;
  message: string;
};

export async function fetchReference(doi: string): Promise<FetchResult> {
  return invoke<FetchResult>("ledger_fetch_reference", { doi });
}

export const OUTPUT_KINDS = ["paper", "talk", "long-form", "release", "note"] as const;
export type OutputKind = (typeof OUTPUT_KINDS)[number];

/** The floor is 20 minutes. */
export const FLOOR_MINUTES = 20;

/** `monday` — lower case, as artboard 02 sets it. */
export function dayName(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const when = new Date(year ?? 1970, (month ?? 1) - 1, day ?? 1);
  return when.toLocaleDateString("en-GB", { weekday: "long" }).toLowerCase();
}

/** `saved 14:22` — the footer's clock, 24-hour, as artboard 02 shows it. */
export function savedAt(epochSeconds: number | null): string | null {
  if (epochSeconds === null) return null;
  const when = new Date(epochSeconds * 1000);
  const hours = String(when.getHours()).padStart(2, "0");
  const minutes = String(when.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
}

/** The footer's size figure: `38.2 MB`, mono, as artboard 02 shows it. */
export function readableSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}
