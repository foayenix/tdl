// The record's prose sections: summary, preparation, benefit-sharing.
//
// Prose sits at 74ch (DESIGN.md §3). Editing is in place: `edit` swaps the
// paragraph for a field, and saving writes through the same command the
// keyboard would.

import { append, el } from "../dom";
import { saveBenefitSharing, saveProse, type BenefitSharing } from "../ledger";

export type ProseSpec = {
  field: "summary" | "preparation";
  title: string;
  text: string | null;
  /** `sources R1, R2, R6` — the references cited in this section. */
  sources: number[];
  /** `rewritten 2026-08-24`, on the summary only. */
  rewritten?: string | null;
};

function sourcesLine(sources: number[], extra?: string | null): HTMLElement | null {
  if (!sources.length && !extra) return null;

  const line = el("div", { class: "prose__meta" });

  if (sources.length) {
    const cited = el("span", {}, "sources ");
    sources.forEach((id, index) => {
      if (index > 0) append(cited, ", ");
      append(cited, el("span", { class: "source-ref" }, `R${id}`));
    });
    append(line, cited);
  }

  if (extra) append(line, el("span", {}, extra));
  return line;
}

export function renderProse(
  spec: ProseSpec,
  monographId: number,
  editing: boolean,
  onToggleEdit: () => void,
  reload: () => void,
  say: (message: string) => void,
): HTMLElement {
  const section = el("section", { class: "section prose" });

  const edit = el(
    "button",
    { type: "button", class: "section__add" },
    editing ? "save" : "edit",
  );

  const head = el(
    "div",
    { class: "section__head" },
    el("span", { class: "section__title" }, spec.title),
    edit,
  );

  append(section, head);

  if (editing) {
    const area = el("textarea", {
      class: "prose__field",
      "aria-label": spec.title,
    }) as HTMLTextAreaElement;
    area.value = spec.text ?? "";
    append(section, area);

    edit.addEventListener("click", () => {
      saveProse(monographId, spec.field, area.value)
        .then(() => {
          onToggleEdit();
          reload();
        })
        .catch((problem) => say(String(problem)));
    });

    setTimeout(() => area.focus(), 0);
  } else {
    append(
      section,
      spec.text
        ? el("p", { class: "prose__body" }, spec.text)
        : el("p", { class: "prose__body prose__body--empty" }, "nothing written yet"),
      sourcesLine(spec.sources, spec.rewritten ? `rewritten ${spec.rewritten}` : null),
    );
    edit.addEventListener("click", onToggleEdit);
  }

  return section;
}

/**
 * Benefit-sharing. It appears on **every** monograph, whether or not there is
 * a record — its absence is a corpus filter flag, so an empty one says it is
 * empty rather than being left off the screen (DESIGN.md §8).
 */
export function renderBenefitSharing(
  monographId: number,
  record: BenefitSharing,
  editing: boolean,
  onToggleEdit: () => void,
  reload: () => void,
  say: (message: string) => void,
): HTMLElement {
  const section = el("section", { class: "section prose" });

  const edit = el(
    "button",
    { type: "button", class: "section__add" },
    editing ? "save" : record.present ? "edit" : "+ record consent",
  );

  append(
    section,
    el(
      "div",
      { class: "section__head" },
      el("span", { class: "section__title" }, "benefit-sharing"),
      record.present
        ? null
        : el("span", { class: "section__unsourced" }, "no agreement recorded"),
      edit,
    ),
  );

  if (editing) {
    const narrative = el("textarea", {
      class: "prose__field",
      "aria-label": "benefit-sharing narrative",
      placeholder: "who the knowledge came from, recorded with consent, under what agreement",
    }) as HTMLTextAreaElement;
    narrative.value = record.narrative ?? "";

    const agreement = el("input", {
      class: "section__field",
      type: "text",
      placeholder: "agreement reference",
      value: record.agreement_ref ?? "",
    }) as HTMLInputElement;

    const expires = el("input", {
      class: "section__field",
      type: "text",
      placeholder: "expires (YYYY-MM)",
      value: record.expires ?? "",
    }) as HTMLInputElement;

    append(
      section,
      narrative,
      el("div", { class: "prose__fields" }, agreement, expires),
    );

    edit.addEventListener("click", () => {
      saveBenefitSharing(monographId, narrative.value, agreement.value, expires.value)
        .then(() => {
          onToggleEdit();
          reload();
        })
        .catch((problem) => say(String(problem)));
    });

    setTimeout(() => narrative.focus(), 0);
    return section;
  }

  append(
    section,
    record.narrative
      ? el("p", { class: "prose__body" }, record.narrative)
      : el(
          "p",
          { class: "prose__body prose__body--empty" },
          "No consent, attribution or agreement is recorded for this record.",
        ),
  );

  if (record.agreement_ref || record.expires) {
    const line = el("div", { class: "prose__meta" });
    append(line, el("span", { class: "prose__on-file" }, "agreement on file"));
    if (record.agreement_ref) append(line, el("span", {}, record.agreement_ref));
    if (record.expires) append(line, el("span", {}, `expires ${record.expires}`));
    append(section, line);
  }

  edit.addEventListener("click", onToggleEdit);
  return section;
}
