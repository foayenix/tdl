// The left nav (artboard 02). 208px fixed, four labelled groups, live counts.

import { append, el } from "./dom";
import type { NavCounts, Status } from "./ledger";
import { readableSize, savedAt } from "./ledger";

export type Route =
  | "today"
  | "corpus"
  | "references"
  | "outputs"
  | "wall"
  | "system";

type Item = {
  route: Route;
  label: string;
  count: (counts: NavCounts) => number | null;
};

type Group = { label: string; items: Item[] };

/** The nav as artboard 02 has it, in order. */
export const GROUPS: Group[] = [
  {
    label: "ledger",
    items: [{ route: "today", label: "Today", count: (c) => c.today_minutes }],
  },
  {
    label: "catalogue",
    items: [
      { route: "corpus", label: "Corpus", count: (c) => c.monographs },
      { route: "references", label: "References", count: (c) => c.references },
    ],
  },
  {
    label: "public",
    items: [
      { route: "outputs", label: "Outputs", count: (c) => c.outputs },
      // The Wall shows the same figure — which is why artboard 02 reads 27 twice.
      { route: "wall", label: "The Wall", count: (c) => c.outputs },
    ],
  },
  {
    label: "system",
    items: [{ route: "system", label: "Tokens", count: () => null }],
  },
];

/** Screens that exist. The rest are disabled until their session lands. */
export const BUILT: ReadonlySet<Route> = new Set<Route>(["today", "system"]);

/** The two mono lines at the foot of the sidebar: path, then size and clock. */
function footer(connected: Status | null, error: string | null): HTMLElement {
  const box = el("div", { class: "sidebar__footer" });

  if (connected === null) {
    // A missing ledger, or one at a schema this build does not read, is a real
    // state with a real instruction — artboard 08 state 1 is the empty case.
    append(box, el("span", { class: "sidebar__footer-line" }, error ?? ""));
    return box;
  }

  const saved = savedAt(connected.last_write);

  // Artboard 02 shows path / size · saved. Artboard 08 state 1 shows the schema
  // too. Both are real, and all four facts will not sit on two lines at 208px —
  // so the schema takes a third line of its own rather than wrapping into one.
  append(
    box,
    el("span", { class: "sidebar__footer-line" }, connected.path),
    el(
      "span",
      { class: "sidebar__footer-line" },
      [readableSize(connected.bytes), saved ? `saved ${saved}` : null]
        .filter((part): part is string => part !== null)
        .join(" · "),
    ),
    el("span", { class: "sidebar__footer-line" }, `schema v${connected.schema_version}`),
  );

  return box;
}

export function renderNav(
  counts: NavCounts | null,
  connected: Status | null,
  error: string | null,
  current: Route,
  go: (route: Route) => void,
): HTMLElement {
  const nav = el("nav", { class: "sidebar" });

  nav.appendChild(
    el(
      "div",
      { class: "sidebar__brand" },
      el("span", { class: "sidebar__title" }, "The Deposit Ledger"),
      el("span", { class: "micro-label sidebar__sub" }, "local · sqlite"),
    ),
  );

  for (const group of GROUPS) {
    const section = el("div", { class: "sidebar__group" });
    section.appendChild(el("span", { class: "sidebar__group-label" }, group.label));

    for (const item of group.items) {
      const built = BUILT.has(item.route);
      const value = counts ? item.count(counts) : null;

      const button = el(
        "button",
        {
          type: "button",
          class: `nav-item${item.route === current ? " is-selected" : ""}`,
          disabled: !built,
          // The count is true whether or not its screen is reachable yet.
          title: built ? undefined : "not built yet",
        },
        el("span", { class: "nav-item__label" }, item.label),
        value === null
          ? el("span", {})
          : el("span", { class: "nav-item__count" }, String(value)),
      );

      if (built) button.addEventListener("click", () => go(item.route));
      section.appendChild(button);
    }

    nav.appendChild(section);
  }

  if (counts && counts.inbox_pending > 0) {
    // "The nav shows a badge when lines are unconsumed" (BUILD.md §5). No
    // artboard places it — the inbox review overlay is v0.2 — so it sits above
    // the footer, out of the nav groups. See STATE.md, session 15.
    nav.appendChild(
      el(
        "div",
        { class: "sidebar__badge" },
        el(
          "span",
          { class: "chip chip--status-drafted" },
          `${counts.inbox_pending} in inbox`,
        ),
      ),
    );
  }

  nav.appendChild(footer(connected, error));

  return nav;
}
