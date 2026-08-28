// Fold the preview build into one file: the CSS and JS inline, the fonts
// already data: URIs from vite. The wrapper supplies <!doctype>, <html>,
// <head> and <body>, so this emits only what goes between them.

import { readFileSync, writeFileSync, readdirSync } from "node:fs";

const html = readFileSync("dist/index.html", "utf8");
const assets = readdirSync("dist/assets");
const css = readFileSync(`dist/assets/${assets.find((f) => f.endsWith(".css"))}`, "utf8");
const js = readFileSync(`dist/assets/${assets.find((f) => f.endsWith(".js"))}`, "utf8");

// Everything between <head> and </body>, with the two <link>/<script src>
// references replaced by their contents, so the page stands on its own.
let out = html
  .replace(/<link[^>]*rel="stylesheet"[^>]*>/g, `<style>\n${css}\n</style>`)
  .replace(
    /<script type="module"[^>]*src="[^"]*"[^>]*><\/script>/,
    `<script type="module">\n${js}\n</script>`,
  );

// The artifact host supplies <!doctype>, <html>, <head> and <body>.
out = out
  .replace(/^[\s\S]*?<head>\n?/, "")
  .replace(/<\/head>\s*<body>\n?/, "")
  .replace(/\s*<\/body>[\s\S]*$/, "\n")
  .replace(/^\s*<meta[^>]*>\n/gm, "");

writeFileSync("dist/preview.html", out);
console.log("wrote dist/preview.html", out.length, "bytes");
