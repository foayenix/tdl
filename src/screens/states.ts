// Artboard 08's states, built as real renders rather than mocks — they are
// what the screens do when the database is in these shapes, not separate
// pages that imitate them.
//
// State 3 (overload) is v0.2 and is not here.

import { append, el } from "../dom";
import { dayName, type BrokenStreak, type Record, type Resolution } from "../ledger";

/**
 * State 1 — first run. 0 rows in every table.
 *
 * Explains what a monograph is, and offers the two ways in. No invented
 * plants: the seed command reads a file you already have.
 */
export function renderFirstRun(onNew: () => void): HTMLElement {
  return el(
    "div",
    { class: "state state--first-run" },
    el("span", { class: "state__count display-num" }, "0"),
    el("span", { class: "state__label label" }, "monographs"),
    el(
      "p",
      { class: "state__prose" },
      "One monograph per plant: binomial, family, part used, indications with " +
        "an evidence level, and a source for every claim.",
    ),
    el(
      "div",
      { class: "state__command" },
      el("span", { class: "state__prompt" }, "$"),
      el("code", {}, "ledger seed --from ~/notes/plants.csv"),
    ),
    el(
      "div",
      { class: "state__actions" },
      el("span", { class: "state__hint" }, "or press"),
      el("span", { class: "keycap" }, "N"),
      el("span", { class: "state__hint" }, "for an empty skeleton record"),
    ),
    (() => {
      const button = el(
        "button",
        { type: "button", class: "button-quiet button-quiet--accent" },
        "New monograph",
      );
      button.addEventListener("click", onNew);
      return button;
    })(),
  );
}

/**
 * State 4 — a name that would not resolve.
 *
 * Shown on the record itself, because that is where the decision is made. The
 * candidates come from GBIF at review time, so this block reports what is
 * stored and offers to ask again; it never shows a name nobody confirmed.
 */
export function renderUnresolvedName(
  monograph: Record,
  queue: { position: number; total: number } | null,
  resolution: Resolution | null,
  onResolve: () => void,
  onAcceptTop: () => void,
  onEnterByHand: () => void,
  onKeepInQueue: () => void,
): HTMLElement | null {
  if (monograph.gbif_key !== null) return null;

  const block = el("div", { class: "state state--unresolved" });

  const head = el("div", { class: "state__head" });
  append(head, el("span", { class: "state__title" }, "name not resolved"));
  if (queue) {
    append(
      head,
      el("span", { class: "state__queue" }, `queue ${queue.position} of ${queue.total}`),
    );
  }
  append(block, head);

  const candidates = resolution?.candidates ?? [];
  const confidence = resolution?.confidence ?? monograph.gbif_confidence;

  append(
    block,
    el(
      "p",
      { class: "state__prose" },
      candidates.length
        ? `Name not resolved — GBIF returned ${candidates.length} ` +
            `${candidates.length === 1 ? "candidate" : "candidates"} below the 0.90 threshold.`
        : confidence === null
          ? "This name has never been checked against GBIF. Nothing has been " +
              "written to the record that GBIF did not confirm."
          : "GBIF's best match was below the 0.90 threshold, so nothing was " +
              "written to the record.",
    ),
  );

  if (confidence !== null) {
    append(
      block,
      el(
        "div",
        { class: "state__meta" },
        "confidence ",
        el("span", { class: "state__value" }, confidence.toFixed(2)),
      ),
    );
  }

  if (resolution && !resolution.accepted && !candidates.length) {
    append(block, el("div", { class: "state__meta" }, resolution.reason));
  }

  // The candidates, with their GBIF keys and scores. Nothing here is written
  // to the record until someone chooses it.
  if (candidates.length) {
    const list = el("div", { class: "state__candidates" });
    for (const candidate of candidates) {
      append(
        list,
        el(
          "div",
          { class: "state__candidate" },
          el("span", { class: "binomial state__value" }, candidate.name ?? "unnamed"),
          el(
            "span",
            { class: "state__meta" },
            candidate.gbif_key === null ? "no key" : String(candidate.gbif_key),
          ),
          el("span", { class: "state__meta" }, candidate.confidence.toFixed(2)),
        ),
      );
    }
    append(block, list);
  }

  const actions = el("div", { class: "state__actions" });

  if (candidates.length) {
    const accept = el("button", { type: "button", class: "button" }, "Accept top match");
    accept.addEventListener("click", onAcceptTop);
    append(actions, accept);
  } else {
    const resolve = el(
      "button",
      { type: "button", class: "button-quiet button-quiet--accent" },
      confidence === null ? "Resolve against GBIF" : "Try GBIF again",
    );
    resolve.addEventListener("click", onResolve);
    append(actions, resolve);
  }

  const byHand = el("button", { type: "button", class: "button-quiet" }, "Enter name by hand");
  byHand.addEventListener("click", onEnterByHand);
  append(actions, byHand);

  if (candidates.length) {
    const keep = el("button", { type: "button", class: "button-quiet" }, "Keep in queue");
    keep.addEventListener("click", onKeepInQueue);
    append(actions, keep);
  }

  append(
    block,
    actions,
    el("span", { class: "state__hint" }, `checked ${monograph.last_touched}`),
  );

  return block;
}

/**
 * State 5 — a broken streak.
 *
 * `longest` stays. The missed days are listed plainly. No flame, no
 * "don't break the chain", no offer to restore it (BUILD.md §8).
 */
export function renderBrokenStreak(
  broken: BrokenStreak,
  onFloorDay: () => void,
  onNextSkeleton: (() => void) | null,
): HTMLElement {
  const missed = broken.missed.length;

  const block = el("div", { class: "state state--broken" });

  append(
    block,
    el(
      "p",
      { class: "state__sentence" },
      `The ${broken.length}-day streak ended on ${broken.ended_on}. ` +
        `${missed} ${missed === 1 ? "day" : "days"} without an entry.`,
    ),
  );

  const days = el("div", { class: "state__days" });
  for (const day of broken.missed) {
    append(
      days,
      el(
        "div",
        { class: "state__day" },
        el("span", { class: "state__day-date" }, day),
        el("span", { class: "state__day-name" }, dayName(day)),
      ),
    );
  }
  append(block, days);

  const floor = el("button", { type: "button", class: "button" }, "Log a floor day — 20 min");
  floor.addEventListener("click", onFloorDay);

  const actions = el("div", { class: "state__actions" }, floor);
  if (onNextSkeleton) {
    const next = el("button", { type: "button", class: "button-quiet" }, "Open next skeleton");
    next.addEventListener("click", onNextSkeleton);
    append(actions, next);
  }
  append(actions, el("span", { class: "state__hint" }, "counting resumes at 1"));
  append(block, actions);

  return block;
}

/**
 * State 6 — a query nothing matches.
 *
 * Says what was searched and how fast, offers the nearest name in the corpus
 * with its edit distance, and offers to open a record for the query itself.
 */
export function renderNoResults(
  query: string,
  searched: { monographs: number; references: number; outputs: number; ms: number },
  nearest: [string, number] | null,
  onNew: (name: string) => void,
): HTMLElement {
  const counted = [
    [searched.monographs, "monograph"],
    [searched.references, "reference"],
    [searched.outputs, "output"],
  ] as const;

  const block = el("div", { class: "state state--no-results" });

  append(
    block,
    el("p", { class: "state__sentence" }, "No monograph, no reference, no output mentions this name."),
    el(
      "div",
      { class: "state__meta" },
      "searched " +
        counted
          .map(([count, noun]) => `${count} ${count === 1 ? noun : `${noun}s`}`)
          .join(" · ") +
        ` · ${searched.ms.toFixed(0)} ms`,
    ),
  );

  if (nearest) {
    const [name, distance] = nearest;
    append(
      block,
      el(
        "div",
        { class: "state__meta" },
        "nearest in corpus: ",
        el("span", { class: "binomial state__value" }, name),
        ` · edit distance ${distance}`,
      ),
    );
  }

  const create = el(
    "button",
    { type: "button", class: "button-quiet button-quiet--accent" },
    `New — ${query}`,
  );
  create.addEventListener("click", () => onNew(query));

  append(
    block,
    el(
      "div",
      { class: "state__actions" },
      create,
      el("span", { class: "state__hint" }, "resolves against GBIF on save"),
    ),
  );

  return block;
}
