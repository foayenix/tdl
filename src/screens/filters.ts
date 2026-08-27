// Artboard 03's 208px filter rail.
//
// Additive across groups, OR within a group: a record shows when it satisfies
// every group that has anything selected. Every selection is in the URL hash.

import { append, el } from "../dom";
import { EVIDENCE, EVIDENCE_LABEL, evidenceCode, type Evidence } from "../evidence";
import type { CorpusRow } from "../ledger";
import { readList, toggleInList } from "../hash";
import { STATUSES } from "../evidence";

/** How many families the rail lists before offering the rest. */
const FAMILIES_SHOWN = 6;

export type Flag = "never-published" | "conservation-concern" | "benefit-sharing-absent";

type Item = {
  value: string;
  label: string;
  count: number;
  /** A filter the schema cannot answer. Rendered, but not offered. */
  disabled?: string;
};

type Group = { key: string; label: string; items: Item[]; more?: string };

function tally<T>(rows: CorpusRow[], of: (row: CorpusRow) => T | null): Map<T, number> {
  const counts = new Map<T, number>();
  for (const row of rows) {
    const value = of(row);
    if (value === null) continue;
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return counts;
}

/** `never published on` — the gap query, per row. */
export function neverPublishedOn(row: CorpusRow): boolean {
  return !row.published && (row.status === "sourced" || row.status === "reviewed");
}

export function groupsFor(rows: CorpusRow[], expandFamilies: boolean): Group[] {
  const statuses = tally(rows, (row) => row.status);
  const families = tally(rows, (row) => row.family);
  const evidence = tally(rows, (row) => row.evidence as Evidence | null);

  const ranked = [...families.entries()].sort(
    (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
  );
  const listed = expandFamilies ? ranked : ranked.slice(0, FAMILIES_SHOWN);

  return [
    {
      key: "status",
      label: "status",
      items: STATUSES.map((status) => ({
        value: status,
        label: status,
        count: statuses.get(status) ?? 0,
      })),
    },
    {
      key: "family",
      label: "family",
      items: listed.map(([family, count]) => ({ value: family, label: family, count })),
      more:
        ranked.length > FAMILIES_SHOWN && !expandFamilies
          ? `all ${ranked.length} families`
          : undefined,
    },
    {
      key: "evidence",
      label: "evidence level",
      items: EVIDENCE.map((level) => ({
        value: level,
        label: `${evidenceCode(level)} ${EVIDENCE_LABEL[level]}`,
        count: evidence.get(level) ?? 0,
      })),
    },
    {
      key: "flag",
      label: "flags",
      items: [
        {
          value: "never-published",
          label: "never published on",
          count: rows.filter(neverPublishedOn).length,
        },
        {
          value: "conservation-concern",
          label: "conservation concern",
          count: 0,
          // schema v4 records no conservation status, and there is no
          // enrichment source for one. Guessing would be inventing botanical
          // data. See STATE.md, session 21.
          disabled: "no conservation data in schema v4",
        },
        {
          value: "benefit-sharing-absent",
          label: "benefit-sharing absent",
          count: rows.filter((row) => !row.benefit_sharing).length,
        },
      ],
    },
  ];
}

/** Additive across groups, OR within a group. */
export function applyFilters(rows: CorpusRow[], params: URLSearchParams): CorpusRow[] {
  const statuses = readList(params, "status");
  const families = readList(params, "family");
  const levels = readList(params, "evidence");
  const flags = readList(params, "flag");

  return rows.filter((row) => {
    if (statuses.length && !statuses.includes(row.status)) return false;
    if (families.length && !(row.family && families.includes(row.family))) return false;
    if (levels.length && !(row.evidence && levels.includes(row.evidence))) return false;

    for (const flag of flags) {
      if (flag === "never-published" && !neverPublishedOn(row)) return false;
      if (flag === "benefit-sharing-absent" && row.benefit_sharing) return false;
      // `conservation-concern` cannot be answered, so it filters nothing —
      // it is never selectable in the first place.
    }

    return true;
  });
}

export function renderFilterRail(
  rows: CorpusRow[],
  params: URLSearchParams,
  expandFamilies: boolean,
  onExpandFamilies: () => void,
): HTMLElement {
  const rail = el("aside", { class: "filter-rail" });

  for (const group of groupsFor(rows, expandFamilies)) {
    const selected = readList(params, group.key);
    const section = el("div", { class: "filter-group" });
    section.appendChild(el("span", { class: "filter-group__label" }, group.label));

    for (const item of group.items) {
      const on = selected.includes(item.value);
      const line = el("label", {
        class:
          `checkbox filter-item${on ? " is-checked" : ""}` +
          (item.disabled ? " is-disabled" : ""),
        title: item.disabled,
      });

      append(
        line,
        el("span", { class: "checkbox__box" }),
        el("span", { class: "checkbox__label filter-item__label" }, item.label),
        el("span", { class: "filter-item__count" }, String(item.count)),
      );

      if (!item.disabled) {
        line.addEventListener("click", () =>
          toggleInList("corpus", params, group.key, item.value),
        );
      }

      section.appendChild(line);
    }

    if (group.more) {
      const more = el("button", { type: "button", class: "filter-more" }, group.more);
      more.addEventListener("click", onExpandFamilies);
      section.appendChild(more);
    }

    rail.appendChild(section);
  }

  return rail;
}
