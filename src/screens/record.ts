// Artboard 05 — the monograph record.
//
// "A corpus table with no detail view is a list of names — the record *is* the
// product" (BUILD.md §1). This screen does not move.

import { append, clear, el } from "../dom";
import { statusChip } from "../chips";
import { EVIDENCE_LABEL, evidenceCode, type Evidence } from "../evidence";
import type { Record } from "../ledger";

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

  // Nothing on the record is editable until sessions 24–27, so there is
  // nothing to save. The button is in its place and says why it is off,
  // rather than being a control that silently does nothing.
  const editable = false;
  const save = el(
    "button",
    {
      type: "button",
      class: "button-quiet button-quiet--accent record__save",
      disabled: !editable,
      title: editable ? undefined : "nothing on this record is editable yet",
    },
    "Save monograph",
  );
  save.addEventListener("click", onSave);
  append(strip, save);

  return strip;
}

export function renderRecord(host: HTMLElement, monograph: Record, onSave: () => void): void {
  clear(host);

  append(
    host,
    header(monograph, onSave),
    // The sections and the sticky rail arrive in sessions 24–27.
    el("div", { class: "record__body" }),
  );
}
