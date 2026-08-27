// The three deposit rows of artboard 02 — `deposit — attach to today`.
//
// Capture friction kills systems like this (BUILD.md §5). Each row is one
// field and one button: type, press, done.

import { append, el } from "../dom";
import { addOutput, openMonograph, OUTPUT_KINDS, type OutputKind } from "../ledger";

export type DepositRow = {
  kind: string;
  placeholder: string;
  /** The 168px slot between the field and the button. */
  meta: () => Node | null;
  button: { label: string; class: string };
  submit: (value: string, meta: HTMLElement) => Promise<void>;
};

function row(spec: DepositRow, reload: () => void, say: (message: string) => void): HTMLElement {
  const field = el("input", {
    class: "deposit__field",
    type: "text",
    placeholder: spec.placeholder,
    "aria-label": spec.kind,
  }) as HTMLInputElement;

  const meta = el("span", { class: "deposit__meta" });
  append(meta, spec.meta());

  const button = el("button", { type: "button", class: spec.button.class }, spec.button.label);

  const submit = async () => {
    const value = field.value.trim();
    if (!value) {
      field.focus();
      return;
    }
    button.setAttribute("disabled", "");
    try {
      await spec.submit(value, meta);
      field.value = "";
      reload();
    } catch (error) {
      say(String(error));
    } finally {
      button.removeAttribute("disabled");
    }
  };

  button.addEventListener("click", () => void submit());
  field.addEventListener("keydown", (event) => {
    if (event.key === "Enter") void submit();
  });

  return el(
    "div",
    { class: "deposit__row" },
    el("span", { class: "deposit__kind" }, spec.kind),
    field,
    meta,
    button,
  );
}

/** The output row's kind chooser, in the meta slot. */
function kindChooser(): { node: HTMLElement; value: () => OutputKind } {
  const select = el("select", { class: "deposit__kind-select", "aria-label": "output kind" });
  for (const kind of OUTPUT_KINDS) {
    select.appendChild(el("option", { value: kind }, kind));
  }
  return { node: select, value: () => (select as HTMLSelectElement).value as OutputKind };
}

export function renderDeposit(reload: () => void, say: (message: string) => void): HTMLElement {
  const chooser = kindChooser();

  const rows: DepositRow[] = [
    {
      kind: "monograph",
      placeholder: "binomial",
      // Artboard 08 state 6's own words for what happens on save.
      meta: () => el("span", {}, "resolves against GBIF on save"),
      button: { label: "Open", class: "button" },
      submit: async (value) => {
        await openMonograph(value);
      },
    },
    {
      kind: "reference",
      placeholder: "doi",
      // Session 19 puts the Crossref result here; until then it stays empty
      // rather than promising something the button does not yet do.
      meta: () => null,
      button: { label: "Fetch", class: "button button--secondary" },
      submit: async () => {
        throw new Error("Fetch arrives in session 19 — use `ledger ref <doi>` meanwhile");
      },
    },
    {
      kind: "output",
      placeholder: "title",
      meta: () => chooser.node,
      button: { label: "Add", class: "button-quiet" },
      submit: async (value) => {
        await addOutput(chooser.value(), value);
      },
    },
  ];

  return el(
    "section",
    { class: "deposit" },
    el("span", { class: "label deposit__label" }, "deposit — attach to today"),
    el("div", { class: "deposit__rows" }, ...rows.map((spec) => row(spec, reload, say))),
  );
}
