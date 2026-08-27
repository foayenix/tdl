// The table primitive. Column widths come from DESIGN.md §7 and are used as
// written: "Use them; do not let content decide."
//
// The rule this file exists to enforce is §6, the unsourced row. A claim row
// without a source is tinted `warn-row`, carries a 2px `secondary` marker on
// its leading edge, and its source cell reads `⚠ source needed` — never blank.

import { append, el } from "./dom";

export type Column = {
  /** Percentage of inner row width (DESIGN.md §7). */
  width: number;
  label: string;
  align?: "right";
  mono?: boolean;
  /** Extra leading space, as the artboard gives the day log's `floor`. */
  padLeft?: number;
  /** The unsourced / selected marker column. Carries no label. */
  marker?: true;
};

export type Cell = string | Node | null;

export type Row = {
  cells: Cell[];
  /** §6. Tints the row, marks its leading edge, and counts in the header. */
  unsourced?: boolean;
  selected?: boolean;
  /** Today's row, or the record in view. */
  focused?: boolean;
  onClick?: () => void;
};

export type TableOptions = {
  compact?: boolean;
  /** 14px horizontal padding — tables inside a record or a narrow panel. */
  inset?: boolean;
  /** A row below the body, inside the card. Artboard 03's corpus counts. */
  footer?: Node;
  /** Off by default. Turn it on only where a row is very wide (DESIGN.md §1). */
  zebra?: boolean;
};

/** The marker column, first, as `mk` in §7's width tables. */
export function markerColumn(width: number): Column {
  return { width, label: "", marker: true };
}

/**
 * A claim row's source cell. Never blank — that is the whole point.
 *
 * Pass the source as the record holds it: a reference id, free text for a
 * field record, or null.
 */
export function sourceCell(source: string | null | undefined): HTMLElement {
  const text = (source ?? "").trim();
  if (text) return el("span", {}, text);
  return el("span", { class: "source-needed" }, "⚠ source needed");
}

function widths(columns: Column[]): string {
  return columns.map((column) => `${column.width}%`).join(" ");
}

export function renderTable(
  columns: Column[],
  rows: Row[],
  options: TableOptions = {},
): HTMLElement {
  const classes = ["table"];
  if (options.compact) classes.push("table--compact");
  if (options.inset) classes.push("table--inset");
  if (options.zebra) classes.push("table--zebra");

  const table = el("div", { class: classes.join(" ") });
  const template = widths(columns);

  const head = el("div", { class: "table__head", style: `grid-template-columns: ${template}` });
  for (const column of columns) {
    head.appendChild(
      el(
        "span",
        {
          class: `table__cell${column.align === "right" ? " table__cell--right" : ""}`,
          style: column.padLeft ? `padding-left: ${column.padLeft}px` : undefined,
        },
        column.marker ? "" : column.label,
      ),
    );
  }
  table.appendChild(head);

  const body = el("div", { class: "table__body" });

  for (const row of rows) {
    const rowClasses = ["table__row"];
    if (row.unsourced) rowClasses.push("is-unsourced");
    if (row.selected) rowClasses.push("is-selected");
    if (row.focused) rowClasses.push("is-focused");

    const node = el(row.onClick ? "button" : "div", {
      class: rowClasses.join(" "),
      style: `grid-template-columns: ${template}`,
      type: row.onClick ? "button" : undefined,
    });

    columns.forEach((column, index) => {
      const cellClasses = ["table__cell"];
      if (column.align === "right") cellClasses.push("table__cell--right");
      if (column.mono) cellClasses.push("numeric");
      if (column.marker) cellClasses.push("table__cell--marker");

      const cell = el("span", {
        class: cellClasses.join(" "),
        style: column.padLeft ? `padding-left: ${column.padLeft}px` : undefined,
      });
      if (column.marker) {
        // §6: a 4 × 16px `secondary` mark in the leading column. Always
        // present, transparent when the row is sourced, so nothing shifts.
        cell.appendChild(el("span", { class: "table__marker" }));
      } else {
        append(cell, row.cells[index] ?? null);
      }
      node.appendChild(cell);
    });

    if (row.onClick) node.addEventListener("click", row.onClick);
    body.appendChild(node);
  }

  table.appendChild(body);
  if (options.footer) table.appendChild(el("div", { class: "table__foot" }, options.footer));
  return table;
}

/** The column width tables, verbatim from DESIGN.md §7. */
export const COLUMNS = {
  // corpus — 936px inner
  corpus: [
    { width: 39.8, label: "accepted name" },
    { width: 12.0, label: "family" },
    { width: 8.8, label: "part" },
    { width: 9.7, label: "status" },
    { width: 3.7, label: "ind", align: "right", mono: true },
    { width: 16.2, label: "evidence" },
    { width: 9.8, label: "first written", align: "right", mono: true },
  ] as Column[],

  // day log — 1148px inner
  dayLog: [
    { width: 8.7, label: "date", mono: true },
    { width: 3.3, label: "day" },
    { width: 4.4, label: "min", align: "right", mono: true },
    { width: 8.0, label: "floor", padLeft: 12 },
    { width: 75.6, label: "deposited" },
  ] as Column[],

  // indications — 904px inner
  indications: [
    markerColumn(0.5),
    { width: 30.8, label: "condition" },
    { width: 12.3, label: "tradition" },
    { width: 12.3, label: "region" },
    { width: 16.6, label: "evidence" },
    { width: 27.5, label: "source" },
  ] as Column[],

  // library — 752px inner
  library: [
    markerColumn(0.4),
    { width: 10.3, label: "status" },
    { width: 44.1, label: "title" },
    { width: 17.0, label: "authors" },
    { width: 22.7, label: "doi", mono: true },
    { width: 5.5, label: "year", align: "right", mono: true },
  ] as Column[],
} as const;
