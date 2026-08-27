// Artboard 02's `last fourteen days`.
//
// Fourteen rows, always — an unlogged day is a row at zero, not a gap, because
// the shape of a fortnight is the thing worth seeing. Today's row is
// `row-focus`.

import { binomial, el } from "../dom";
import type { DayLog, DayRow } from "../ledger";
import { COLUMNS, renderTable } from "../table";

/** What was deposited, as names and counts. Blank on a day with nothing. */
function deposited(day: DayRow): Node | null {
  const parts: Node[] = [];

  for (const name of day.monographs) {
    if (parts.length) parts.push(document.createTextNode(" · "));
    parts.push(binomial(name));
  }

  const counts: string[] = [];
  if (day.references > 0) {
    counts.push(`${day.references} ${day.references === 1 ? "reference" : "references"}`);
  }
  for (const kind of day.outputs) counts.push(kind);

  for (const count of counts) {
    if (parts.length) parts.push(document.createTextNode(" · "));
    parts.push(document.createTextNode(count));
  }

  if (!parts.length) return null;

  const wrap = document.createDocumentFragment();
  for (const part of parts) wrap.appendChild(part);
  return wrap;
}

export function renderDayLog(log: DayLog): HTMLElement {
  const rows = log.days.map((day) => ({
    cells: [
      day.date,
      el("span", { class: "daylog__dow" }, day.dow),
      // A day with no entry is blank; a day logged at 0 minutes reads 0.
      day.logged ? String(day.minutes) : "",
      // The floor is a success: the word in `secondary`, never a red mark,
      // never an empty bar (DESIGN.md §8).
      day.floor_day ? el("span", { class: "daylog__floor" }, "floor") : null,
      deposited(day),
    ],
    focused: day.is_today,
  }));

  return el(
    "section",
    { class: "daylog" },
    el(
      "div",
      { class: "daylog__head" },
      el("span", { class: "label" }, "last fourteen days"),
      el(
        "span",
        { class: "daylog__summary" },
        `${log.total_minutes.toLocaleString("en-GB")} min · ${log.average} avg · ` +
          `${log.floor_days} ${log.floor_days === 1 ? "floor day" : "floor days"}`,
      ),
    ),
    // Zebra on: the day log is the one place DESIGN.md §1 allows it, because
    // the rows are very wide.
    renderTable(COLUMNS.dayLog, rows, { inset: true, zebra: true }),
  );
}
