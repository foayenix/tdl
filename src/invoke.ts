// One place that decides whether a command goes to Rust or to the preview stub.
//
// The preview build swaps this module's implementation at build time (see
// vite.config.ts); in the app it is Tauri's own `invoke` and nothing else.

import { invoke as tauriInvoke } from "@tauri-apps/api/core";

export function invoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  return tauriInvoke<T>(command, args);
}
