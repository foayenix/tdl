// The only way the frontend reaches the database is through a Rust command.
// It holds no shell permission and opens no connection of its own.
import { invoke } from "@tauri-apps/api/core";

export type Status = {
  path: string;
  bytes: number;
  schema_version: number;
};

export async function status(): Promise<Status> {
  return invoke<Status>("ledger_status");
}

/** The footer's size figure: `38.2 MB`, mono, as artboard 02 shows it. */
export function readableSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}
