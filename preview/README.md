# The read-only browser preview

`dist/preview.html` is the app's own frontend — the same screens, the same
CSS, the same modules — over a frozen set of answers instead of a live Rust
core. It exists so the app can be looked at without building it.

Two things are swapped, and only two:

- `./invoke` resolves to `src/invoke.preview.ts` instead of `src/invoke.ts`,
  so commands are answered from `data.json` rather than by Tauri.
- `data.json` is injected into the page as `window.__LEDGER_PREVIEW__`.

Everything else is byte-for-byte the app's. A preview that had its own copy of
a screen would drift from the screen it previews, and then be worth nothing.

## Where the answers come from

`src-tauri/src/bin/preview_dump.rs` calls the same library functions the window
calls, against a real SQLite file, and writes what they returned:

    just preview-data /tmp/demo.sqlite

So the numbers on the preview are query results, not invented. What they are
query results *about* is a scratch ledger of nine plants — demo data, never a
real one. Point `preview-data` at a scratch database only: its answers end up
in a file that gets published.

## Building it

    just preview

`PREVIEW=1` turns on the plugin in `vite.config.ts`, which also raises the asset
inline limit so the woff2 faces go in as `data:` URIs, and mirrors the dark
tokens into `@media (prefers-color-scheme: dark)` — the app owns its own root
and switches on `:root[data-theme]`, but a page embedded in a host has a third
state where nothing is stamped and only the OS says which theme to render.

## What it cannot do

Write. Every command that would change the database falls through to a
`PreviewOnly` error, which the app reports where the click happened. A standing
line at the foot of the page says so before anything is clicked.
