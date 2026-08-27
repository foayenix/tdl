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
