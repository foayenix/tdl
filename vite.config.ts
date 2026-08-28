import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";

/** The read-only browser preview (`PREVIEW=1 npm run build`).
 *
 * Two changes, and only two: `./invoke` resolves to the stub that answers from
 * a dump instead of calling Rust, and that dump is injected into the page. The
 * screens, the CSS and every other module are byte-for-byte the app's own — a
 * preview that diverged from the thing it previews would be worth nothing. */
function preview(): Plugin {
  const stub = resolve(__dirname, "src/invoke.preview.ts");
  const data = readFileSync(resolve(__dirname, "preview/data.json"), "utf8");

  // The app switches themes on `:root[data-theme]`, which is all it needs —
  // it owns its own root. A page embedded in a host has a third state: the
  // viewer left the choice on "system", so nothing is stamped and only the
  // OS says which theme to render. Mirror the dark tokens into that state,
  // read out of tokens.css rather than restated, so they cannot drift.
  const tokens = readFileSync(resolve(__dirname, "src/styles/tokens.css"), "utf8");
  const dark = tokens.slice(tokens.indexOf(':root[data-theme="dark"] {'));
  const body = dark.slice(dark.indexOf("{") + 1, dark.indexOf("\n}"));

  return {
    name: "ledger-preview",
    enforce: "pre",
    resolveId(source) {
      return source === "./invoke" || source.endsWith("/src/invoke.ts") ? stub : null;
    },
    transformIndexHtml(html) {
      const json = data.replace(/</g, "\\u003c");
      const system = `@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) {${body}\n  }\n}`;
      return html.replace(
        "</head>",
        `  <style>${system}</style>\n  <script>window.__LEDGER_PREVIEW__ = ${json};</script>\n  </head>`,
      );
    },
  };
}

// The frontend is vanilla DOM and hand-written CSS. No framework plugin here,
// and there is not going to be one — see STATE.md, session 12.
export default defineConfig({
  root: "src",
  plugins: process.env.PREVIEW ? [preview()] : [],
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    target: "safari15",
    cssCodeSplit: false,
    // The preview ships as one file, so the fonts go in as data: URIs.
    assetsInlineLimit: process.env.PREVIEW ? 1024 * 1024 : 4096,
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
