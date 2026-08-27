// Artboard 02 — today. Opens on launch.
//
// The floor is 20 minutes and a floor day is a success. The interface must
// never render one as a shortfall: the word `floor` in `secondary`, never a red
// mark, never an empty bar (DESIGN.md §8). Nothing on this screen counts down.

import { append, clear, el } from "../dom";
import {
  dayName,
  setFloorDay,
  type DayLog,
  type SavedNote,
  type TodayStats,
} from "../ledger";
import { renderDayLog } from "./daylog";
import { renderDeposit } from "./deposit";
import { renderNote } from "./note";

/** `current streak 41 days` — label muted, the number in ink at 13px. */
function stat(label: string, value: number, suffix?: string): HTMLElement {
  return el(
    "span",
    { class: "stat" },
    label,
    " ",
    el("span", { class: "stat__value" }, String(value)),
    suffix ? ` ${suffix}` : null,
  );
}

function head(stats: TodayStats): HTMLElement {
  return el(
    "header",
    { class: "screen-head" },
    el(
      "div",
      { class: "screen-head__title" },
      el("h1", { class: "board-title" }, "Today"),
      el("span", { class: "screen-head__date" }, `${stats.date} · ${dayName(stats.date)}`),
    ),
    el(
      "div",
      { class: "stat-row" },
      stat("current streak", stats.current_streak, stats.current_streak === 1 ? "day" : "days"),
      stat("longest", stats.longest_streak),
      el(
        "span",
        { class: "stat" },
        "floor met ",
        el("span", { class: "stat__value" }, String(stats.floor_met)),
        ` / ${stats.days_logged}`,
      ),
    ),
  );
}

/** The yes/no segmented control. Selected is `ink`, not the accent. */
function floorToggle(stats: TodayStats, reload: () => void): HTMLElement {
  const segment = (label: string, on: boolean) => {
    const button = el(
      "button",
      {
        type: "button",
        class: `segment${stats.floor_day === on ? " is-selected" : ""}`,
        "aria-pressed": stats.floor_day === on,
      },
      label,
    );
    button.addEventListener("click", () => {
      if (stats.floor_day === on) return;
      void setFloorDay(on).then(reload);
    });
    return button;
  };

  return el(
    "div",
    { class: "floor" },
    el("span", { class: "label" }, "20-minute floor day"),
    el("div", { class: "segmented" }, segment("yes", true), segment("no", false)),
  );
}

function minutesWorked(stats: TodayStats, reload: () => void): HTMLElement {
  return el(
    "div",
    { class: "today__minutes" },
    el(
      "div",
      { class: "measure" },
      el("span", { class: "label" }, "minutes worked"),
      el(
        "div",
        { class: "measure__value" },
        el("span", { class: "display-num" }, String(stats.minutes)),
        el("span", { class: "measure__unit" }, "min"),
      ),
    ),
    floorToggle(stats, reload),
  );
}

export function renderToday(
  host: HTMLElement,
  stats: TodayStats,
  saved: SavedNote,
  log: DayLog,
  reload: () => void,
): void {
  clear(host);

  // Anything the interface could not do says so here rather than failing quietly.
  const trouble = el("div", { class: "trouble" });
  const say = (message: string) => {
    trouble.textContent = message;
  };

  append(
    host,
    head(stats),
    trouble,
    el(
      "div",
      { class: "today__card" },
      minutesWorked(stats, reload),
      renderNote(saved, say),
    ),
    renderDeposit(reload, say),
    renderDayLog(log),
  );
}
