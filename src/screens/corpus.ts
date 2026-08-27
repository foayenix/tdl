// Artboard 03 — the corpus.
//
// The footer's `9 never published on` is the gap query, and BUILD.md §4 says
// it is permanently visible. It is not behind a filter and it does not go away
// when it reads zero.

import { append, binomial, clear, el } from "../dom";
import { evidenceChip, statusChip } from "../chips";
import type { Evidence } from "../evidence";
import type { Corpus, CorpusRow } from "../ledger";
import { applyFilters, renderFilterRail } from "./filters";
import { COLUMNS, renderTable } from "../table";

function nameCell(row: CorpusRow): Node {
  const cell = el("span", { class: "corpus__name" });
  if (row.accepted_name === null) {
    // A record whose name has not resolved still has to be findable.
    append(cell, el("span", { class: "corpus__unnamed" }, "unnamed skeleton"));
    return cell;
  }
  append(cell, binomial(row.accepted_name, row.authority));
  return cell;
}

/** Whether the family group is showing all of them. Not filter state — a
 *  disclosure — so it does not belong in the URL. */
let familiesExpanded = false;

export function renderCorpus(
  host: HTMLElement,
  data: Corpus,
  params: URLSearchParams,
  open: (id: number) => void,
  reload: () => void,
): void {
  clear(host);

  const visible = applyFilters(data.rows, params);
  const shown = visible.length;

  const rows = visible.map((row) => ({
    cells: [
      nameCell(row),
      row.family ?? "",
      el("span", { class: "corpus__part" }, row.part ?? ""),
      statusChip(row.status, "sm"),
      row.indications === 0 ? "" : String(row.indications),
      row.evidence ? evidenceChip(row.evidence as Evidence, "sm") : null,
      el("span", { class: "corpus__written" }, row.first_written),
    ],
    onClick: () => open(row.id),
  }));

  const screen = el("div", { class: "corpus" });

  append(
    screen,
    el(
      "header",
      { class: "screen-head" },
      el(
        "div",
        { class: "screen-head__title" },
        el("h1", { class: "board-title" }, "Corpus"),
        el(
          "span",
          { class: "screen-head__date" },
          `${data.total} ${data.total === 1 ? "monograph" : "monographs"} · ` +
            `${shown} shown · sorted by first written`,
        ),
      ),
    ),
    renderTable(COLUMNS.corpus, rows, {
      footer: el(
        "div",
        { class: "corpus__footer" },
        el(
          "span",
          { class: "corpus__counts" },
          `${shown} of ${data.total} · ${data.indications} ` +
            `${data.indications === 1 ? "indication" : "indications"} · ` +
            `${data.never_published_on} never published on`,
        ),
        el(
          "button",
          { type: "button", class: "button-quiet button-quiet--accent" },
          "New monograph",
        ),
      ),
    }),
  );

  append(
    host,
    renderFilterRail(data.rows, params, familiesExpanded, () => {
      familiesExpanded = true;
      reload();
    }),
    screen,
  );
}
