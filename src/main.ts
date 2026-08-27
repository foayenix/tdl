import { append, clear, el } from "./dom";
import {
  brokenStreak,
  corpus,
  dayLog,
  navCounts,
  nearestName,
  nextSkeleton,
  note,
  openMonograph,
  queuePosition,
  record,
  resolveName,
  setNameByHand,
  status,
  todayStats,
} from "./ledger";
import type { BrokenStreak, Corpus, DayLog, NavCounts, SavedNote, Status, TodayStats } from "./ledger";
import { readHash } from "./hash";
import { BUILT, renderNav, type Route } from "./nav";
import { renderSystem } from "./screens/system";
import { renderCorpus } from "./screens/corpus";
import { renderRecord } from "./screens/record";
import { renderToday } from "./screens/today";

/** The last GBIF answer, so its candidate list survives a redraw. */
let lastResolution: import("./ledger").Resolution | null = null;

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
  broken: BrokenStreak | null;
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
      broken: await brokenStreak(),
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
      broken: null,
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
    broken,
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

  /** Open a skeleton for a name — the way in from the empty and no-result states. */
  const openNew = (name: string) => {
    const wanted = name.trim() || window.prompt("binomial")?.trim();
    if (!wanted) return;
    void openMonograph(wanted).then((id) => {
      window.location.hash = `/monograph?id=${id}`;
    });
  };

  if (today && saved && log && route === "today") {
    const skeleton = broken ? await nextSkeleton().catch(() => null) : null;
    renderToday(
      screen,
      today,
      saved,
      log,
      broken,
      skeleton === null
        ? null
        : () => {
            window.location.hash = `/monograph?id=${skeleton}`;
          },
      () => void render(),
    );
  }
  else if (route === "corpus" && catalogue) {
    const query = readHash().params.get("find") ?? "";
    const nearest = query ? await nearestName(query).catch(() => null) : null;
    renderCorpus(
      screen,
      catalogue,
      readHash().params,
      (id) => {
        window.location.hash = `/monograph?id=${id}`;
      },
      () => void render(),
      openNew,
      nearest,
    );
  } else if (route === "monograph") {
    const id = Number(readHash().params.get("id"));
    if (Number.isFinite(id) && id > 0) {
      try {
        const monograph = await record(id);
        const queue = await queuePosition(id).catch(() => null);
        const name = monograph.accepted_name;

        await renderRecord(
          screen,
          monograph,
          queue,
          // Held between renders so the candidate list survives a redraw.
          lastResolution,
          () => void render(),
          {
            // Resolving is the sidecar's job — Rust has no HTTP client.
            resolve: () => {
              if (!name) return;
              void resolveName(name).then((result) => {
                lastResolution = result;
                void render();
              });
            },
            acceptTop: () => {
              if (!name) return;
              void resolveName(name, true).then(() => {
                lastResolution = null;
                void render();
              });
            },
            enterByHand: () => {
              const typed = window.prompt("binomial", name ?? "")?.trim();
              if (!typed) return;
              void setNameByHand(id, typed).then(() => {
                lastResolution = null;
                void render();
              });
            },
            keepInQueue: () => {
              lastResolution = null;
              void render();
            },
          },
          () => void render(),
        );
      } catch (problem) {
        append(screen, el("div", { class: "trouble" }, String(problem)));
      }
    } else {
      append(screen, el("div", { class: "trouble" }, "no monograph named in the address"));
    }
  } else if (route === "system") renderSystem(screen);
  else if (error) append(screen, el("div", { class: "trouble" }, error));
}

// `N` opens an empty skeleton, as artboard 08 state 1 offers. Not while
// something is being typed into — a note or a field owns its own keystrokes.
window.addEventListener("keydown", (event) => {
  if (event.key !== "n" && event.key !== "N") return;
  if (event.metaKey || event.ctrlKey || event.altKey) return;

  const focused = document.activeElement;
  const typing =
    focused instanceof HTMLInputElement ||
    focused instanceof HTMLTextAreaElement ||
    focused instanceof HTMLSelectElement;
  if (typing) return;

  event.preventDefault();
  const wanted = window.prompt("binomial")?.trim();
  if (!wanted) return;
  void openMonograph(wanted).then((id) => {
    window.location.hash = `/monograph?id=${id}`;
  });
});

window.addEventListener("hashchange", () => void render());
void render();
