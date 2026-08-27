// Artboard 01 — the component library, rendered live from the CSS variables.
// Build this first; every later screen is assembled from parts proven here.
//
// The species and citations below are the artboard's own fixtures. §8 permits
// them here and nowhere else: "design fixtures for artboard 01 only — never
// seed data."

import { append, binomial, clear, el } from "../dom";
import { COLUMNS, renderTable, sourceCell } from "../table";

const COLOUR_GROUPS: Array<[string, string[]]> = [
  ["ground", ["ground", "surface", "inset", "zebra", "row-focus", "row-hover"]],
  ["ink", ["ink", "muted", "hairline", "outline"]],
  ["accent", ["primary", "primary-wash", "primary-ring"]],
  ["build / caution", ["secondary", "secondary-wash", "secondary-ring"]],
  ["signal", ["positive", "critical", "warn-row"]],
  ["disabled", ["disabled", "disabled-ink"]],
];

const TYPE_SPECIMENS: Array<[string, string, string]> = [
  ["board-title", "Fraunces 600 / 22", "System"],
  ["record-name", "Fraunces 600i / 26", "Prunus africana"],
  ["section-head", "Fraunces 600 / 17", "Corpus & monographs"],
  [
    "body",
    "Plex Sans 400 / 13.5",
    "Bark decoction, standardised extract; 9 indications recorded, strongest evidence meta-analysis.",
  ],
  ["table-cell", "Plex Sans 400 / 13", "Standardised extract · stem bark"],
  ["emphasis", "Plex Sans 500 / 12", "3 rows unsourced"],
  ["numeric", "Plex Mono 400 / 11.5", "2026-08-24 · 10.1016/j.jep.2025.118914 · 96 min"],
  ["label", "Plex Mono 400 / 10 · .14em", "field label · accepted name"],
  ["micro-label", "Plex Mono 400 / 9.5 · .12em", "wfo-id · gbif key"],
  ["display-num", "Plex Mono 400 / 44", "96"],
];

const STATUSES = ["skeleton", "drafted", "sourced", "reviewed"] as const;

const EVIDENCE: Array<[string, string, number]> = [
  ["E1", "traditional only", 0],
  ["E2", "in vitro", 1],
  ["E3", "in vivo", 1],
  ["E4", "human uncontrolled", 2],
  ["E5", "RCT", 3],
  ["E6", "meta-analysis", 3],
];

const STATES = ["default", "hover", "focus", "selected", "disabled"] as const;

function panel(title: string, note: string, body: HTMLElement): HTMLElement {
  return el(
    "section",
    { class: "specimen" },
    el(
      "header",
      { class: "specimen__head" },
      el("span", { class: "label" }, title),
      el("span", { class: "micro-label specimen__note" }, note),
    ),
    body,
  );
}

/** A dash means the state does not apply — DESIGN.md §4 says so explicitly. */
function dash(): HTMLElement {
  return el("span", { class: "specimen__dash micro-label" }, "—");
}

function stateGrid(rows: Array<[string, Array<HTMLElement | null>]>): HTMLElement {
  const grid = el("div", { class: "state-grid" });

  append(grid, el("span", {}));
  for (const state of STATES) append(grid, el("span", { class: "micro-label" }, state));

  for (const [name, cells] of rows) {
    append(grid, el("span", { class: "micro-label state-grid__name" }, name));
    for (const cell of cells) append(grid, el("span", { class: "state-grid__cell" }, cell ?? dash()));
  }

  return grid;
}

function colours(): HTMLElement {
  const wrap = el("div", { class: "swatches" });

  for (const [group, tokens] of COLOUR_GROUPS) {
    append(
      wrap,
      el(
        "div",
        { class: "swatches__group" },
        el("span", { class: "micro-label" }, group),
        el(
          "div",
          { class: "swatches__row" },
          ...tokens.map((token) =>
            el(
              "div",
              { class: "swatch" },
              el("span", { class: "swatch__chip", style: `background: var(--${token})` }),
              el("span", { class: "swatch__name micro-label" }, token),
            ),
          ),
        ),
      ),
    );
  }

  return wrap;
}

function type(): HTMLElement {
  return el(
    "div",
    { class: "type-ramp" },
    ...TYPE_SPECIMENS.flatMap(([role, spec, sample]) => [
      el("span", { class: "micro-label type-ramp__spec" }, spec),
      role === "record-name"
        ? el("span", { class: role }, binomial(sample))
        : el("span", { class: role }, sample),
    ]),
  );
}

function buttons(): HTMLElement {
  const primary = (extra: string, disabled = false) =>
    el("button", { class: `button ${extra}`.trim(), disabled, type: "button" }, "Save entry");

  const quiet = (extra: string, disabled = false) =>
    el("button", { class: `button-quiet ${extra}`.trim(), disabled, type: "button" }, "+ add");

  return stateGrid([
    ["primary", [primary(""), primary("is-hover"), primary("is-focus"), null, primary("", true)]],
    [
      "quiet",
      [
        quiet(""),
        quiet("is-hover"),
        quiet("is-focus"),
        quiet("is-selected"),
        quiet("", true),
      ],
    ],
    [
      "secondary",
      [
        el("button", { class: "button button--secondary", type: "button" }, "Draft with model"),
        null,
        null,
        null,
        null,
      ],
    ],
  ]);
}

function navItem(extra = "", disabled = false): HTMLElement {
  return el(
    "button",
    { class: `nav-item ${extra}`.trim(), disabled, type: "button" },
    el("span", { class: "nav-item__label" }, "Corpus"),
    el("span", { class: "nav-item__count" }, "38"),
  );
}

function checkbox(extra = ""): HTMLElement {
  return el(
    "label",
    { class: `checkbox ${extra}`.trim() },
    el("span", { class: "checkbox__box" }),
    el("span", { class: "checkbox__label" }, "drafted"),
  );
}

function keycap(extra = ""): HTMLElement {
  return el("span", { class: `keycap ${extra}`.trim() }, "1");
}

function chips(): HTMLElement {
  return el(
    "div",
    { class: "chip-rows" },
    el("span", { class: "micro-label" }, "status pill — monograph"),
    el(
      "div",
      { class: "chip-row" },
      ...STATUSES.map((status) => el("span", { class: `chip chip--status-${status}` }, status)),
    ),
    el("span", { class: "micro-label" }, "evidence chip — six levels on a four-step ramp"),
    el(
      "div",
      { class: "chip-row" },
      ...EVIDENCE.map(([code, label, step]) =>
        el(
          "span",
          { class: `chip chip--ev${step}` },
          el("span", { class: "chip__code" }, code),
          " ",
          label,
        ),
      ),
    ),
    el("span", { class: "micro-label" }, "severity — safety rows"),
    el(
      "div",
      { class: "chip-row" },
      ...["critical", "caution", "note"].map((severity) =>
        el("span", { class: `chip chip--severity-${severity}` }, severity),
      ),
    ),
    el("span", { class: "micro-label" }, "reading state — references"),
    el(
      "div",
      { class: "chip-row" },
      ...["read", "reading", "queued"].map((state) =>
        el("span", { class: `chip chip--read-${state}` }, state),
      ),
    ),
    el("span", { class: "micro-label" }, "output kind"),
    el(
      "div",
      { class: "chip-row" },
      ...["paper", "talk", "long-form", "release", "note"].map((kind) =>
        el("span", { class: `kind kind--${kind}` }, kind),
      ),
    ),
  );
}

/** Artboard 01's `table row — monograph`, at the corpus column widths. */
function corpusRows(): HTMLElement {
  return renderTable(COLUMNS.corpus, [
    {
      cells: [
        binomial("Prunus africana", "(Hook.f.) Kalkman"),
        "Rosaceae",
        "stem bark",
        el("span", { class: "chip chip--status-reviewed" }, "reviewed"),
        "9",
        el(
          "span",
          { class: "chip chip--ev3" },
          el("span", { class: "chip__code" }, "E6"),
          " meta-analysis",
        ),
        "2026-08-24",
      ],
    },
    {
      cells: [
        binomial("Khaya senegalensis", "(Desr.) A.Juss."),
        "Meliaceae",
        "stem bark",
        el("span", { class: "chip chip--status-drafted" }, "drafted"),
        "3",
        el(
          "span",
          { class: "chip chip--ev1" },
          el("span", { class: "chip__code" }, "E3"),
          " in vivo",
        ),
        "2026-08-24",
      ],
      focused: true,
    },
  ]);
}

/**
 * The unsourced row (DESIGN.md §6) at the indication column widths — the rule
 * every claim table in the application obeys.
 */
function unsourcedRows(): HTMLElement {
  return renderTable(COLUMNS.indications, [
    {
      cells: [
        null,
        "benign prostatic hyperplasia",
        "European phytotherapy",
        "France, Germany",
        el(
          "span",
          { class: "chip chip--ev3" },
          el("span", { class: "chip__code" }, "E6"),
          " meta-analysis",
        ),
        sourceCell("R2"),
      ],
    },
    {
      cells: [
        null,
        "urinary retention",
        "Kikuyu",
        "central Kenya",
        el(
          "span",
          { class: "chip chip--ev0" },
          el("span", { class: "chip__code" }, "E1"),
          " traditional only",
        ),
        sourceCell(null),
      ],
      unsourced: true,
    },
    {
      cells: [
        null,
        "inflammatory joint pain",
        "Hausa",
        "northern Nigeria",
        el(
          "span",
          { class: "chip chip--ev1" },
          el("span", { class: "chip__code" }, "E2"),
          " in vitro",
        ),
        sourceCell("field notes 2025-11"),
      ],
    },
  ], { inset: true });
}

export function renderSystem(host: HTMLElement): void {
  clear(host);

  append(
    host,
    el(
      "header",
      { class: "screen-head" },
      el("h1", { class: "board-title" }, "System"),
      el("span", { class: "micro-label" }, "tokens · type · components"),
    ),
    el(
      "div",
      { class: "specimens" },
      panel("colour", "literal · no derivation at runtime", colours()),
      panel("type", "three families · self-hosted woff2", type()),
      panel("buttons", "primary · quiet · secondary", buttons()),
      panel(
        "left nav",
        "selected adds a fill and a bar",
        stateGrid([
          [
            "nav item",
            [
              navItem(),
              navItem("is-hover"),
              navItem("is-focus"),
              navItem("is-selected"),
              navItem("", true),
            ],
          ],
        ]),
      ),
      panel(
        "checkbox · keycap",
        "keycap has no hover state",
        stateGrid([
          [
            "checkbox",
            [
              checkbox(),
              checkbox("is-hover"),
              checkbox("is-focus"),
              checkbox("is-checked"),
              checkbox("is-disabled"),
            ],
          ],
          [
            "keycap",
            [keycap(), null, keycap("is-focus"), keycap("is-selected"), keycap("is-disabled")],
          ],
        ]),
      ),
      panel(
        "text input",
        "doi",
        el("input", {
          class: "field",
          type: "text",
          value: "10.1016/j.jep.2025.118914",
          size: 30,
        }),
      ),
      panel("chips", "status · evidence · severity · reading · kind", chips()),
      panel("table row — monograph", "widths from DESIGN.md §7 · today's row is row-focus", corpusRows()),
      panel(
        "the unsourced row",
        "warn-row tint · 4 × 16 secondary mark · never a blank source cell",
        unsourcedRows(),
      ),
    ),
  );
}
