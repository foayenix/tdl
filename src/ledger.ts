// The only way the frontend reaches the database is through a Rust command.
// It holds no shell permission and opens no connection of its own.
import { invoke } from "./invoke";

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

export type WallOutput = {
  id: number;
  kind: string;
  title: string;
  venue: string | null;
  date: string;
  url: string | null;
  plants: string[];
};

export type Wall = {
  outputs: WallOutput[];
  total: number;
  earliest: string | null;
  latest: string | null;
  by_kind: [string, number][];
};

export async function wall(): Promise<Wall> {
  return invoke<Wall>("ledger_wall");
}

export type BrokenStreak = {
  ended_on: string;
  length: number;
  missed: string[];
};

export async function brokenStreak(): Promise<BrokenStreak | null> {
  return invoke<BrokenStreak | null>("ledger_broken_streak");
}

export type QueuePosition = { position: number; total: number };

export async function queuePosition(id: number): Promise<QueuePosition | null> {
  return invoke<QueuePosition | null>("ledger_queue_position", { id });
}

export async function nextSkeleton(): Promise<number | null> {
  return invoke<number | null>("ledger_next_skeleton");
}

export type BoundReference = {
  position: number;
  reference_id: number;
  title: string;
  authors: string | null;
  journal: string | null;
  year: number | null;
  doi: string | null;
  read_state: string;
  added_at: string;
  sections: string[];
};

export async function recordReferences(id: number): Promise<BoundReference[]> {
  return invoke<BoundReference[]>("ledger_record_references", { id });
}

export type CitingOutput = {
  id: number;
  kind: string;
  title: string;
  venue: string | null;
  date: string;
};

export async function citedByOutputs(id: number): Promise<CitingOutput[]> {
  return invoke<CitingOutput[]>("ledger_cited_by_outputs", { id });
}

export type QueuedReading = { count: number; oldest: string | null };

export async function queuedReading(id: number): Promise<QueuedReading> {
  return invoke<QueuedReading>("ledger_queued_reading", { id });
}

export async function unsourcedBySection(id: number): Promise<[string, number][]> {
  return invoke<[string, number][]>("ledger_unsourced_by_section", { id });
}

export type BenefitSharing = {
  narrative: string | null;
  agreement_ref: string | null;
  expires: string | null;
  consent_recorded_at: string | null;
  present: boolean;
};

export async function benefitSharing(id: number): Promise<BenefitSharing> {
  return invoke<BenefitSharing>("ledger_benefit_sharing", { id });
}

export async function saveBenefitSharing(
  id: number,
  narrative: string | null,
  agreementRef: string | null,
  expires: string | null,
): Promise<BenefitSharing> {
  return invoke<BenefitSharing>("ledger_save_benefit_sharing", {
    id,
    narrative,
    agreementRef,
    expires,
  });
}

export async function saveProse(id: number, field: string, text: string): Promise<Record> {
  return invoke<Record>("ledger_save_prose", { id, field, text });
}

export async function sectionSources(id: number, section: string): Promise<number[]> {
  return invoke<number[]>("ledger_section_sources", { id, section });
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

export type Candidate = {
  name: string | null;
  gbif_key: number | null;
  confidence: number;
};

export type Resolution = {
  accepted: boolean;
  reason: string;
  confidence: number | null;
  name: string | null;
  candidates: Candidate[];
};

export async function resolveName(name: string, accept = false): Promise<Resolution> {
  return invoke<Resolution>("ledger_resolve_name", { name, accept });
}

export async function setNameByHand(id: number, name: string): Promise<Record> {
  return invoke<Record>("ledger_set_name_by_hand", { id, name });
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
