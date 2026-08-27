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

export async function navCounts(): Promise<NavCounts> {
  return invoke<NavCounts>("ledger_nav_counts");
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
