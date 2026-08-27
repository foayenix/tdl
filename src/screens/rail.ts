// Artboard 05's 224px right rail, sticky to the top of the record.
//
// A jump list with counts, the unsourced ones in `secondary`; what this plant
// has been published in; and what is still waiting to be read.

import { append, el } from "../dom";
import type { CitingOutput, QueuedReading } from "../ledger";

export type RailSection = {
  anchor: string;
  label: string;
  count: number | null;
  unsourced: number;
};

export function renderRail(
  sections: RailSection[],
  outputs: CitingOutput[],
  queued: QueuedReading,
): HTMLElement {
  const rail = el("aside", { class: "record-rail" });

  const jump = el("nav", { class: "rail__group" });
  append(jump, el("span", { class: "rail__label" }, "in this record"));

  for (const section of sections) {
    const line = el("a", { class: "rail__jump", href: `#${section.anchor}` });
    append(line, el("span", { class: "rail__jump-label" }, section.label));

    const count = el("span", { class: "rail__jump-count" });
    if (section.count !== null) append(count, String(section.count));
    // The unsourced count follows into the rail (DESIGN.md §6).
    if (section.unsourced > 0) {
      append(count, " · ", el("span", { class: "rail__unsourced" }, String(section.unsourced)));
    }
    append(line, count);

    // The jump list scrolls the record rather than changing the address —
    // the hash belongs to the corpus filters.
    line.addEventListener("click", (event) => {
      event.preventDefault();
      document.getElementById(section.anchor)?.scrollIntoView({ block: "start" });
    });

    append(jump, line);
  }

  append(rail, jump);

  const cited = el("div", { class: "rail__group" });
  append(cited, el("span", { class: "rail__label" }, "cited by your outputs"));

  if (outputs.length) {
    for (const output of outputs) {
      append(
        cited,
        el(
          "div",
          { class: "rail__output" },
          el("span", { class: `kind kind--${output.kind}` }, output.kind),
          el("span", { class: "rail__output-date" }, output.date),
          el("span", { class: "rail__output-title" }, output.title),
          output.venue ? el("span", { class: "rail__output-venue" }, output.venue) : null,
        ),
      );
    }
  } else {
    // This is the gap query, per record. It is the corpus footer's
    // `9 never published on` seen from the other end, and it is not softened.
    append(cited, el("span", { class: "rail__none" }, "never published on"));
  }

  append(rail, cited);

  if (queued.count > 0) {
    append(
      rail,
      el(
        "div",
        { class: "rail__group" },
        el(
          "span",
          { class: "rail__queued" },
          `${queued.count} ${queued.count === 1 ? "reference" : "references"} queued, unread →`,
        ),
        queued.oldest
          ? el("span", { class: "rail__none" }, `oldest queued ${queued.oldest}`)
          : null,
      ),
    );
  }

  return rail;
}
