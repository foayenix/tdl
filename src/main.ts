import { readableSize, status } from "./ledger";

// Session 12 is the window and the connection, nothing more. The tokens land
// in session 13 and the components in 14; until then this screen exists to
// prove the app opened the right file at the right schema.
async function render(): Promise<void> {
  const app = document.querySelector<HTMLElement>("#app");
  if (!app) return;

  try {
    const connected = await status();
    app.textContent =
      `${connected.path} · ${readableSize(connected.bytes)} · ` +
      `schema v${connected.schema_version}`;
  } catch (error) {
    // A ledger that is missing or at the wrong schema is a real state with a
    // real instruction, not a crash. Artboard 08 state 1 is the empty case.
    app.textContent = String(error);
  }
}

void render();
