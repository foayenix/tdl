// The autosaving note of artboard 02.
//
// Two seconds of quiet and it writes; the explicit `Save entry` writes at once.
// Both go through the same command, so the footer can never claim a save that
// did not happen.

import { append, el } from "../dom";
import { saveNote, type SavedNote } from "../ledger";

const DEBOUNCE_MS = 2000;

export function renderNote(saved: SavedNote, say: (message: string) => void): HTMLElement {
  const area = el("textarea", {
    class: "note__body",
    "aria-label": "note",
    spellcheck: true,
  }) as HTMLTextAreaElement;
  area.value = saved.note;

  const footer = el("span", { class: "note__saved" });
  const button = el("button", { type: "button", class: "button" }, "Save entry");

  let entryId = saved.entry_id;
  let timer: number | undefined;
  let inFlight = false;
  let lastWritten = saved.note;

  const report = (at: string) => {
    footer.textContent = `autosaved ${at} · entry ${entryId.toLocaleString("en-GB")}`;
  };

  if (saved.saved_at) report(saved.saved_at);

  const write = async () => {
    if (inFlight) return;
    const text = area.value;
    if (text === lastWritten) return;

    inFlight = true;
    try {
      const result = await saveNote(text);
      entryId = result.entry_id;
      lastWritten = text;
      report(result.saved_at);
    } catch (error) {
      // Say it, do not swallow it. An autosave that silently failed is worse
      // than one that never ran.
      footer.textContent = "not saved";
      say(String(error));
    } finally {
      inFlight = false;
    }
  };

  area.addEventListener("input", () => {
    footer.textContent = "unsaved";
    window.clearTimeout(timer);
    timer = window.setTimeout(() => void write(), DEBOUNCE_MS);
  });

  // Leaving the field is a stronger signal than two seconds of quiet.
  area.addEventListener("blur", () => {
    window.clearTimeout(timer);
    void write();
  });

  button.addEventListener("click", () => {
    window.clearTimeout(timer);
    void write();
  });

  const panel = el("div", { class: "note" });
  append(
    panel,
    el("span", { class: "label note__label" }, "note"),
    area,
    el("div", { class: "note__footer" }, footer, button),
  );

  return panel;
}
