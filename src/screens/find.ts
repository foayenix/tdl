// Artboard 03's `find` box — FTS5 behind it, the hit count beside it.
//
// The query is filter state, so it lives in the hash like the rest. It is
// written with `replaceState` rather than by assigning to the hash: a live
// search would otherwise put every keystroke in the back stack.

import { append, el } from "../dom";
import { replaceParam } from "../hash";
import { search, type SearchResult } from "../ledger";

const DEBOUNCE_MS = 120;

export function renderFind(
  query: string,
  found: SearchResult | null,
  onChange: (query: string, result: SearchResult | null) => void,
): HTMLElement {
  const input = el("input", {
    class: "find__input",
    type: "search",
    value: query,
    placeholder: "find",
    "aria-label": "find",
    spellcheck: false,
  }) as HTMLInputElement;

  const count = el("span", { class: "find__count" });
  if (found && query) {
    count.textContent = `${found.hits} ${found.hits === 1 ? "hit" : "hits"}`;
  }

  let timer: number | undefined;

  const run = async () => {
    const text = input.value.trim();
    replaceParam("corpus", new URLSearchParams(window.location.hash.split("?")[1] ?? ""), "find", text);

    if (!text) {
      count.textContent = "";
      onChange("", null);
      return;
    }

    const result = await search(text);
    count.textContent = `${result.hits} ${result.hits === 1 ? "hit" : "hits"}`;
    onChange(text, result);
  };

  input.addEventListener("input", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => void run(), DEBOUNCE_MS);
  });

  // `esc` clears, as artboard 08 state 6 says it does.
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      input.value = "";
      window.clearTimeout(timer);
      void run();
    }
  });

  const box = el("div", { class: "find" });
  append(box, el("span", { class: "find__label" }, "find"), input, count);
  return box;
}
