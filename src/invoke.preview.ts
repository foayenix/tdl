// The preview build's `invoke`. Swapped in for `src/invoke.ts` by
// vite.config.ts when PREVIEW=1; the app never loads this file.

import { previewInvoke } from "./preview";

export function invoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  return previewInvoke<T>(command, args);
}
