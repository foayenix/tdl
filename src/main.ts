import { append, clear, el } from "./dom";
import { dayLog, navCounts, note, status, todayStats } from "./ledger";
import type { DayLog, NavCounts, SavedNote, Status, TodayStats } from "./ledger";
import { BUILT, renderNav, type Route } from "./nav";
import { renderSystem } from "./screens/system";
import { renderToday } from "./screens/today";

function routeFromHash(): Route {
  const hash = window.location.hash.replace(/^#\/?/, "");
  // Today opens on launch (DESIGN.md §8).
  return BUILT.has(hash as Route) ? (hash as Route) : "today";
}

type Loaded = {
  status: Status | null;
  counts: NavCounts | null;
  today: TodayStats | null;
  note: SavedNote | null;
  log: DayLog | null;
  error: string | null;
};

async function load(): Promise<Loaded> {
  try {
    return {
      status: await status(),
      counts: await navCounts(),
      today: await todayStats(),
      note: await note(),
      log: await dayLog(),
      error: null,
    };
  } catch (error) {
    // A ledger that is missing, or at a schema this build does not read, is a
    // real state with a real instruction. The message says which.
    return {
      status: null,
      counts: null,
      today: null,
      note: null,
      log: null,
      error: String(error),
    };
  }
}

async function render(): Promise<void> {
  const app = document.querySelector<HTMLElement>("#app");
  if (!app) return;

  const route = routeFromHash();
  const { status: connected, counts, today, note: saved, log, error } = await load();

  clear(app);

  const screen = el("main", { class: "app-content" });

  // The footer lives at the foot of the sidebar, not in a bar across the
  // window — artboard 02 puts it there.
  append(
    app,
    renderNav(counts, connected, error, route, (next) => {
      window.location.hash = `/${next}`;
    }),
    screen,
  );

  if (route === "today" && today && saved && log) {
    renderToday(screen, today, saved, log, () => void render());
  }
  else if (route === "system") renderSystem(screen);
  else if (error) append(screen, el("div", { class: "trouble" }, error));
}

window.addEventListener("hashchange", () => void render());
void render();
