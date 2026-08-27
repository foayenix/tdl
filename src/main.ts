import { append, clear, el } from "./dom";
import { corpus, dayLog, navCounts, note, record, status, todayStats } from "./ledger";
import type { Corpus, DayLog, NavCounts, SavedNote, Status, TodayStats } from "./ledger";
import { readHash } from "./hash";
import { BUILT, renderNav, type Route } from "./nav";
import { renderSystem } from "./screens/system";
import { renderCorpus } from "./screens/corpus";
import { renderRecord } from "./screens/record";
import { renderToday } from "./screens/today";

function routeFromHash(): Route {
  // Today opens on launch (DESIGN.md §8).
  const { route } = readHash();
  return BUILT.has(route as Route) ? (route as Route) : "today";
}

type Loaded = {
  status: Status | null;
  counts: NavCounts | null;
  today: TodayStats | null;
  note: SavedNote | null;
  log: DayLog | null;
  corpus: Corpus | null;
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
      corpus: await corpus(),
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
      corpus: null,
      error: String(error),
    };
  }
}

async function render(): Promise<void> {
  const app = document.querySelector<HTMLElement>("#app");
  if (!app) return;

  const route = routeFromHash();
  const {
    status: connected,
    counts,
    today,
    note: saved,
    log,
    corpus: catalogue,
    error,
  } = await load();

  clear(app);

  // The corpus puts a filter rail beside the content; the shell holds both.
  const screen = el("main", {
    class:
      route === "corpus"
        ? "app-content app-content--railed"
        : route === "monograph"
          ? "app-content app-content--record"
          : "app-content",
  });

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
  else if (route === "corpus" && catalogue) {
    renderCorpus(
      screen,
      catalogue,
      readHash().params,
      (id) => {
        window.location.hash = `/monograph?id=${id}`;
      },
      () => void render(),
    );
  } else if (route === "monograph") {
    const id = Number(readHash().params.get("id"));
    if (Number.isFinite(id) && id > 0) {
      record(id)
        .then((monograph) => renderRecord(screen, monograph, () => void render()))
        .catch((problem) => append(screen, el("div", { class: "trouble" }, String(problem))));
    } else {
      append(screen, el("div", { class: "trouble" }, "no monograph named in the address"));
    }
  } else if (route === "system") renderSystem(screen);
  else if (error) append(screen, el("div", { class: "trouble" }, error));
}

window.addEventListener("hashchange", () => void render());
void render();
