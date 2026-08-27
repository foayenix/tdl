// Artboard 05 — the monograph record.
//
// "A corpus table with no detail view is a list of names — the record *is* the
// product" (BUILD.md §1). This screen does not move.

import { append, clear, el } from "../dom";
import { evidenceChip, severityChip, statusChip } from "../chips";
import { EVIDENCE, EVIDENCE_LABEL, evidenceCode, type Evidence } from "../evidence";
import { SEVERITY } from "../evidence";
import { benefitSharing, claims, sectionSources, type Claim, type Record } from "../ledger";
import { renderBenefitSharing, renderProse } from "./prose";
import { renderSection, type SectionSpec } from "./section";
import { COLUMNS } from "../table";

/** `wfo-id wfo-0000651773` — label muted, value ink. Blank when unknown. */
function identity(label: string, value: string | null, extraClass?: string): HTMLElement {
  const line = el("span", { class: `identity__line${extraClass ? ` ${extraClass}` : ""}` });
  append(line, `${label} `);

  if (value === null || value === "") {
    // An identifier nobody has established yet reads as absent, not as empty
    // space. `wfo_id` is NULL for every record in v0.1 — see STATE.md.
    append(line, el("span", { class: "identity__absent" }, "not resolved"));
  } else {
    append(line, el("span", { class: "identity__value" }, value));
  }

  return line;
}

function header(monograph: Record, onSave: () => void): HTMLElement {
  const title = el("div", { class: "record__title" });
  append(
    title,
    monograph.accepted_name
      ? el("span", { class: "record-name" }, monograph.accepted_name)
      : el("span", { class: "record__unnamed" }, "unnamed skeleton"),
    // The authority is never italic, and here it is Fraunces 16 upright.
    monograph.authority ? el("span", { class: "record__authority" }, monograph.authority) : null,
    statusChip(monograph.status),
  );

  const provenance = el("div", { class: "record__provenance" });
  const parts = [monograph.family, monograph.part].filter(
    (part): part is string => Boolean(part),
  );
  for (const part of parts) {
    append(provenance, el("span", {}, part), el("span", { class: "record__slash" }, "/"));
  }
  if (monograph.habitat_note) {
    append(provenance, el("span", { class: "record__habitat" }, monograph.habitat_note));
  }

  return el(
    "header",
    { class: "record__head" },
    el(
      "div",
      { class: "record__head-row" },
      el(
        "div",
        { class: "record__identity-left" },
        el("span", { class: "record__crumb" }, `corpus › monograph ${monograph.id}`),
        title,
        provenance,
      ),
      el(
        "div",
        { class: "identity" },
        identity("wfo-id", monograph.wfo_id),
        identity(
          "gbif key",
          monograph.gbif_key === null ? null : String(monograph.gbif_key),
        ),
        identity("first written", monograph.first_written, "identity__line--spaced"),
        identity("last touched", monograph.last_touched),
      ),
    ),
    summaryStrip(monograph, onSave),
  );
}

/** `7 indications · 19 references bound · strongest evidence E5 RCT · 3 rows unsourced` */
function summaryStrip(monograph: Record, onSave: () => void): HTMLElement {
  const strip = el("div", { class: "record__strip" });

  const dot = () => el("span", { class: "record__dot" }, "·");

  append(
    strip,
    el(
      "span",
      {},
      `${monograph.indications} ${monograph.indications === 1 ? "indication" : "indications"}`,
    ),
    dot(),
    el(
      "span",
      {},
      `${monograph.references_bound} ` +
        `${monograph.references_bound === 1 ? "reference" : "references"} bound`,
    ),
  );

  if (monograph.strongest_evidence) {
    const level = monograph.strongest_evidence as Evidence;
    append(
      strip,
      dot(),
      el(
        "span",
        {},
        "strongest evidence ",
        el(
          "span",
          { class: "record__strip-value" },
          `${evidenceCode(level)} ${EVIDENCE_LABEL[level]}`,
        ),
      ),
    );
  }

  // The unsourced count follows into the header (DESIGN.md §6). It is shown
  // whenever it is not zero, and never softened.
  if (monograph.unsourced > 0) {
    append(
      strip,
      dot(),
      el(
        "span",
        { class: "record__unsourced" },
        `${monograph.unsourced} ${monograph.unsourced === 1 ? "row" : "rows"} unsourced`,
      ),
    );
  }

  // Artboard 05 puts a `Save monograph` here, which implies a form: edit, then
  // commit. Every edit on this screen writes through at the moment it is made —
  // an added claim row, a saved prose section — so there is never anything
  // pending for it to commit. It stays in its place and says so rather than
  // pretending to do work. See STATE.md, session 26: this is a design question.
  const save = el(
    "button",
    {
      type: "button",
      class: "button-quiet button-quiet--accent record__save",
      disabled: true,
      title: "every change on this record is written as you make it",
    },
    "Save monograph",
  );
  save.addEventListener("click", onSave);
  append(strip, save);

  return strip;
}

/** The sections of artboard 05 that exist. 25–27 add the rest. */
const SECTIONS: SectionSpec[] = [
  {
    table: "vernacular",
    title: "vernacular names",
    addLabel: "+ add name",
    columns: COLUMNS.vernacular,
    placeholders: ["name", "language", "region"],
    meta: (rows) => {
      const languages = new Set(
        rows.map((row) => row.cells[1]).filter((value): value is string => Boolean(value)),
      );
      return languages.size
        ? `${languages.size} ${languages.size === 1 ? "language" : "languages"}`
        : null;
    },
  },
  {
    table: "indication",
    title: "indications",
    addLabel: "+ add indication",
    columns: COLUMNS.indications,
    placeholders: ["condition", "tradition", "region", "evidence"],
    // `evidence` is one of six named values; a blank is not one of them.
    choices: { 3: EVIDENCE },
    // A claim is who used it for what, where — the evidence chip carries the
    // level, and the code beside it keeps the exact one recoverable.
    cell: (claim, index) =>
      index === 3 && claim.cells[3]
        ? evidenceChip(claim.cells[3] as Evidence, "sm")
        : (claim.cells[index] ?? ""),
    meta: (rows) => {
      const levels = rows
        .map((row) => row.cells[3])
        .filter((value): value is string => Boolean(value));
      if (!levels.length) return null;
      const codes = levels.map((level) => evidenceCode(level as Evidence)).sort();
      const lowest = codes[0] ?? "";
      const highest = codes[codes.length - 1] ?? "";
      return lowest === highest ? lowest : `${lowest} → ${highest}`;
    },
  },
  {
    table: "constituent",
    title: "constituents",
    addLabel: "+ add compound",
    columns: COLUMNS.constituent,
    placeholders: ["compound", "class", "InChIKey"],
    meta: (rows) => {
      const classes = new Set(
        rows.map((row) => row.cells[1]).filter((value): value is string => Boolean(value)),
      );
      return classes.size ? [...classes].sort().join(", ") : null;
    },
  },
  {
    table: "safety",
    title: "safety",
    addLabel: "+ add finding",
    columns: COLUMNS.safety,
    placeholders: ["kind", "finding", "severity"],
    // `severity` is one of three named values, like `evidence`.
    choices: { 2: SEVERITY },
    cell: (claim, index) =>
      index === 2 && claim.cells[2]
        ? severityChip(claim.cells[2], "sm")
        : (claim.cells[index] ?? ""),
    meta: (rows) => {
      const critical = rows.filter((row) => row.cells[2] === "critical").length;
      // A critical finding is worth naming in the heading; the others are not.
      return critical ? `${critical} critical` : null;
    },
  },
];

/** Which section, if any, has its inline add row open. */
let addingIn: string | null = null;

/** Which prose section, if any, is being edited. */
let editingProse: string | null = null;

export async function renderRecord(
  host: HTMLElement,
  monograph: Record,
  onSave: () => void,
  reload: () => void,
): Promise<void> {
  clear(host);

  const trouble = el("div", { class: "trouble" });
  const say = (message: string) => {
    trouble.textContent = message;
  };

  const body = el("div", { class: "record__body" });
  const column = el("div", { class: "record__column" });
  append(body, column);

  append(host, header(monograph, onSave), trouble, body);

  // Artboard 05's order: summary, then the claim sections, then preparation
  // and benefit-sharing.
  const summarySources = await sectionSources(monograph.id, "summary").catch(() => []);
  column.appendChild(
    renderProse(
      {
        field: "summary",
        title: "summary",
        text: monograph.summary,
        sources: summarySources,
        rewritten: monograph.summary_rewritten_at,
      },
      monograph.id,
      editingProse === "summary",
      () => {
        editingProse = editingProse === "summary" ? null : "summary";
        reload();
      },
      reload,
      say,
    ),
  );

  for (const spec of SECTIONS) {
    let rows: Claim[] = [];
    try {
      rows = await claims(monograph.id, spec.table);
    } catch (error) {
      say(String(error));
    }

    column.appendChild(
      renderSection(
        spec,
        monograph.id,
        rows,
        addingIn === spec.table,
        () => {
          addingIn = addingIn === spec.table ? null : spec.table;
          reload();
        },
        () => {
          addingIn = null;
          reload();
        },
        say,
      ),
    );
  }

  const preparationSources = await sectionSources(monograph.id, "preparation").catch(() => []);
  column.appendChild(
    renderProse(
      {
        field: "preparation",
        title: "preparation",
        text: monograph.preparation,
        sources: preparationSources,
      },
      monograph.id,
      editingProse === "preparation",
      () => {
        editingProse = editingProse === "preparation" ? null : "preparation";
        reload();
      },
      reload,
      say,
    ),
  );

  // Benefit-sharing is not optional chrome; it appears on every record.
  const consent = await benefitSharing(monograph.id).catch(() => null);
  if (consent) {
    column.appendChild(
      renderBenefitSharing(
        monograph.id,
        consent,
        editingProse === "benefit_sharing",
        () => {
          editingProse = editingProse === "benefit_sharing" ? null : "benefit_sharing";
          reload();
        },
        reload,
        say,
      ),
    );
  }
}
