import { append, clear, el } from "./dom";
import { navCounts, status } from "./ledger";
import type { NavCounts, Status } from "./ledger";
import { BUILT, renderNav, type Route } from "./nav";
import { renderSystem } from "./screens/system";

// Screens land one per session. Until a route has one, its nav item is
// disabled — a real state in DESIGN.md §4, not a placeholder screen.
const SCREENS: Partial<Record<Route, (host: HTMLElement) => void>> = {
  system: renderSystem,
};

function routeFromHash(): Route {
  const hash = window.location.hash.replace(/^#\/?/, "");
  return BUILT.has(hash as Route) ? (hash as Route) : "system";
}

async function load(): Promise<{ status: Status | null; counts: NavCounts | null; error: string | null }> {
  try {
    return { status: await status(), counts: await navCounts(), error: null };
  } catch (error) {
    // A ledger that is missing, or at a schema this build does not read, is a
    // real state with a real instruction. The message says which.
    return { status: null, counts: null, error: String(error) };
  }
}

async function render(): Promise<void> {
  const app = document.querySelector<HTMLElement>("#app");
  if (!app) return;

  const route = routeFromHash();
  const { status: connected, counts, error } = await load();

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

  SCREENS[route]?.(screen);
}

window.addEventListener("hashchange", () => void render());
void render();
