// Artboard 04 — The Wall. The trophy cabinet.
//
// No pagination. No load-more. The length of the scroll is the point
// (DESIGN.md §8), so everything published is on one page in one order.

import { append, binomial, clear, el } from "../dom";
import type { Wall, WallOutput } from "../ledger";

/**
 * The plants a card is about, italic. An output about no particular plant
 * reads `whole corpus`, **upright and muted** — never italic, because it is
 * not a name.
 */
function plants(output: WallOutput): HTMLElement {
  const line = el("span", { class: "card__plants" });

  if (!output.plants.length) {
    append(line, el("span", { class: "card__no-plant" }, "whole corpus"));
    return line;
  }

  output.plants.forEach((name, index) => {
    if (index > 0) append(line, ", ");
    append(line, binomial(name));
  });

  return line;
}

function card(output: WallOutput): HTMLElement {
  return el(
    "article",
    { class: "card" },
    el(
      "div",
      { class: "card__head" },
      el("span", { class: `kind kind--${output.kind}` }, output.kind),
      el("span", { class: "card__date" }, output.date),
    ),
    el("h3", { class: "card__title" }, output.title),
    output.venue ? el("span", { class: "card__venue" }, output.venue) : null,
    plants(output),
  );
}

function yearsOf(outputs: WallOutput[]): Array<[string, WallOutput[]]> {
  const years = new Map<string, WallOutput[]>();
  for (const output of outputs) {
    const year = output.date.slice(0, 4);
    const group = years.get(year);
    if (group) group.push(output);
    else years.set(year, [output]);
  }
  // The query is already newest first, so insertion order is the right order.
  return [...years.entries()];
}

export function renderWall(host: HTMLElement, data: Wall): void {
  clear(host);

  const span =
    data.earliest && data.latest && data.earliest !== data.latest
      ? `${data.earliest} → ${data.latest}`
      : (data.latest ?? "");

  append(
    host,
    el(
      "header",
      { class: "screen-head" },
      el(
        "div",
        { class: "screen-head__title" },
        el("h1", { class: "board-title" }, "The Wall"),
        el(
          "span",
          { class: "screen-head__date" },
          [
            `${data.total} ${data.total === 1 ? "output" : "outputs"}`,
            span || null,
            "newest first",
          ]
            .filter((part): part is string => Boolean(part))
            .join(" · "),
        ),
      ),
      el(
        "div",
        { class: "wall__kinds" },
        ...data.by_kind.map(([kind, count]) =>
          el(
            "span",
            { class: "wall__kind" },
            el("span", { class: `kind kind--${kind}` }, `${kind}s`),
            el("span", { class: "wall__kind-count" }, String(count)),
          ),
        ),
      ),
    ),
  );

  if (!data.outputs.length) {
    append(
      host,
      el(
        "p",
        { class: "prose__body prose__body--empty" },
        "Nothing published yet. The wall fills from `ledger win`, or the " +
          "output row on Today.",
      ),
    );
    return;
  }

  for (const [year, outputs] of yearsOf(data.outputs)) {
    append(
      host,
      el(
        "section",
        { class: "wall__year" },
        el(
          "div",
          { class: "wall__year-head" },
          el("span", { class: "wall__year-label" }, year),
          el("span", { class: "wall__year-count" }, String(outputs.length)),
        ),
        el("div", { class: "wall__cards" }, ...outputs.map(card)),
      ),
    );
  }
}
