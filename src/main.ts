import { el, append, clear } from "./dom";
import { renderSystem } from "./screens/system";
import { readableSize, status } from "./ledger";

// The left nav arrives in session 15. Until then the app opens on artboard 01,
// which is the screen every later screen is assembled from.
async function footer(): Promise<HTMLElement> {
  const line = el("footer", { class: "app-footer micro-label" });

  try {
    const connected = await status();
    append(
      line,
      `${connected.path} · ${readableSize(connected.bytes)} · schema v${connected.schema_version}`,
    );
  } catch (error) {
    // A missing ledger or a schema this build does not read is a real state
    // with a real instruction, not a crash.
    append(line, String(error));
  }

  return line;
}

async function render(): Promise<void> {
  const app = document.querySelector<HTMLElement>("#app");
  if (!app) return;

  clear(app);
  const screen = el("div", { class: "app-content" });
  append(app, screen, await footer());
  renderSystem(screen);
}

void render();
