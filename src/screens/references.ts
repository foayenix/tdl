// Artboard 05's references section: `R1`–`Rn`, the citation, the DOI, the
// reading state.
//
// The R-number is a position within this record, not the library's row id —
// a record's sixth reference is R6 whether the library holds twelve or twelve
// hundred.

import { append, el } from "../dom";
import { readStateChip } from "../chips";
import type { BoundReference } from "../ledger";

/** `Okonkwo, Mbeki & Laurent · 2025 · Journal of Ethnopharmacology` */
function citation(reference: BoundReference): HTMLElement {
  const line = el("span", { class: "reference__meta" });
  const parts = [reference.authors, reference.year ? String(reference.year) : null, reference.journal]
    .filter((part): part is string => Boolean(part));
  append(line, parts.join(" · "));
  return line;
}

export function renderReferences(references: BoundReference[]): HTMLElement {
  const section = el("section", { class: "section", id: "section-references" });

  append(
    section,
    el(
      "div",
      { class: "section__head" },
      el("span", { class: "section__title" }, "references"),
      el(
        "span",
        { class: "section__count" },
        `${references.length} bound`,
      ),
    ),
  );

  if (!references.length) {
    append(
      section,
      el("p", { class: "prose__body prose__body--empty" }, "No reference is bound to this record."),
    );
    return section;
  }

  const list = el("div", { class: "reference-list" });

  for (const reference of references) {
    append(
      list,
      el(
        "div",
        { class: "reference" },
        el("span", { class: "reference__number" }, `R${reference.position}`),
        el(
          "div",
          { class: "reference__body" },
          el("span", { class: "reference__title" }, reference.title),
          citation(reference),
          reference.doi ? el("span", { class: "reference__doi" }, reference.doi) : null,
        ),
        el(
          "div",
          { class: "reference__side" },
          readStateChip(reference.read_state, "sm"),
          reference.sections.length
            ? el("span", { class: "reference__sections" }, reference.sections.join(" · "))
            : null,
        ),
      ),
    );
  }

  append(section, list);
  return section;
}

/**
 * The block at the foot of the record. DESIGN.md §6's closing line, and the
 * database is what actually enforces it — the trigger from session 06.
 */
export function renderReviewedStatus(unsourced: number, status: string): HTMLElement {
  if (unsourced === 0) {
    return el(
      "div",
      { class: "reviewed-block reviewed-block--clear" },
      el("span", { class: "reviewed-block__count" }, "every claim row is sourced"),
      el(
        "span",
        {},
        status === "reviewed"
          ? "This record is reviewed."
          : "Status can advance to reviewed.",
      ),
    );
  }

  return el(
    "div",
    { class: "reviewed-block" },
    el(
      "span",
      { class: "reviewed-block__count" },
      `${unsourced} ${unsourced === 1 ? "row" : "rows"} unsourced`,
    ),
    el(
      "span",
      {},
      "Status cannot advance to ",
      el("span", { class: "reviewed-block__status" }, "reviewed"),
      " while any claim row is missing a source.",
    ),
  );
}
