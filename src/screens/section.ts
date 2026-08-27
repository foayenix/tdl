// A section of the record: a heading with a count, a `+ add` button, a table
// with per-row sourcing, and an inline add row.
//
// Every claim table on artboard 05 has this shape, so it is built once.

import { append, el } from "../dom";
import { addClaim, type Claim } from "../ledger";
import { renderTable, sourceCell, type Cell, type Column } from "../table";

export type SectionSpec = {
  table: string;
  /** The heading, e.g. `vernacular names`. */
  title: string;
  /** The `+ add` button's label, e.g. `+ add name`. */
  addLabel: string;
  columns: Column[];
  /** A one-line summary beside the count, e.g. `5 languages`. */
  meta?: (rows: Claim[]) => string | null;
  /** How each claim column renders. Falls back to the raw cell text. */
  cell?: (claim: Claim, index: number) => Cell;
  /** Placeholders for the inline add row, one per claim column. */
  placeholders: string[];
  /**
   * Columns that are an enum rather than free text, by claim-column index.
   * A blank is not one of the values a CHECK constraint accepts, so those
   * columns get a chooser rather than a field — the record cannot offer to
   * write something the database will refuse.
   */
  choices?: Record<number, readonly string[]>;
};

/** `R7`, free text, or the warning. Never blank (DESIGN.md §6). */
function source(claim: Claim): HTMLElement {
  if (claim.source_reference_id !== null) {
    return el("span", { class: "source-ref" }, `R${claim.source_reference_id}`);
  }
  return sourceCell(claim.source_note);
}

/** `7 · 1 unsourced` — the count, with the unsourced part in `secondary`. */
function heading(spec: SectionSpec, rows: Claim[], onAdd: () => void): HTMLElement {
  const unsourced = rows.filter((row) => row.source_reference_id === null &&
    !(row.source_note ?? "").trim()).length;

  const count = el("span", { class: "section__count" }, String(rows.length));
  if (unsourced > 0) {
    append(
      count,
      " · ",
      el("span", { class: "section__unsourced" }, `${unsourced} unsourced`),
    );
  } else {
    const meta = spec.meta?.(rows);
    if (meta) append(count, ` · ${meta}`);
  }

  const add = el("button", { type: "button", class: "section__add" }, spec.addLabel);
  add.addEventListener("click", onAdd);

  return el(
    "div",
    { class: "section__head" },
    el("span", { class: "section__title" }, spec.title),
    count,
    add,
  );
}

/** The inline add row: one field per claim column, plus a source field. */
function addRow(
  spec: SectionSpec,
  monographId: number,
  reload: () => void,
  say: (message: string) => void,
): HTMLElement {
  const claimColumns = spec.columns.filter((column) => !column.marker);
  const fields: HTMLInputElement[] = [];

  const row = el("div", {
    class: "section__add-row",
    style: `grid-template-columns: ${spec.columns.map((c) => `${c.width}%`).join(" ")}`,
  });

  // The marker column, empty, so the fields line up with the rows above.
  append(row, el("span", {}));

  const controls: Array<HTMLInputElement | HTMLSelectElement> = [];

  claimColumns.forEach((column, index) => {
    const isSource = column.label === "source";
    const choices = spec.choices?.[index];

    if (choices) {
      const select = el("select", {
        class: "section__field",
        "aria-label": column.label,
      }) as HTMLSelectElement;
      for (const choice of choices) {
        select.appendChild(el("option", { value: choice }, choice));
      }
      controls.push(select);
      append(row, el("span", { class: "section__field-cell" }, select));
      return;
    }

    const field = el("input", {
      class: "section__field",
      type: "text",
      placeholder: isSource ? "source" : (spec.placeholders[index] ?? column.label),
      "aria-label": column.label,
    }) as HTMLInputElement;
    fields.push(field);
    controls.push(field);
    append(row, el("span", { class: "section__field-cell" }, field));
  });

  const submit = async () => {
    const values = controls.slice(0, controls.length - 1).map((control) => control.value);
    const note = controls[controls.length - 1]?.value ?? "";
    try {
      await addClaim(monographId, spec.table, values, note || null);
      reload();
    } catch (error) {
      say(String(error));
    }
  };

  for (const control of controls) {
    control.addEventListener("keydown", (event) => {
      if ((event as KeyboardEvent).key === "Enter") void submit();
    });
  }

  // The row is not in the document yet — `focus()` on a detached element does
  // nothing, and the keystrokes go to whatever was focused before, which is
  // how `enter` ends up pressing a nav button.
  setTimeout(() => controls[0]?.focus(), 0);

  return row;
}

export function renderSection(
  spec: SectionSpec,
  monographId: number,
  rows: Claim[],
  adding: boolean,
  onToggleAdd: () => void,
  reload: () => void,
  say: (message: string) => void,
): HTMLElement {
  const body = rows.map((claim) => ({
    cells: spec.columns.map((column, index): Cell => {
      if (column.marker) return null;
      if (column.label === "source") return source(claim);
      // The marker column shifts the claim columns by one.
      const claimIndex = index - 1;
      return spec.cell?.(claim, claimIndex) ?? claim.cells[claimIndex] ?? "";
    }),
    unsourced:
      claim.source_reference_id === null && !(claim.source_note ?? "").trim(),
  }));

  const table = renderTable(spec.columns, body, { inset: true });
  if (adding) {
    table.appendChild(addRow(spec, monographId, reload, say));
  }

  return el(
    "section",
    { class: "section" },
    heading(spec, rows, onToggleAdd),
    table,
  );
}
