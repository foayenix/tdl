import { defineConfig } from "vite";

// The frontend is vanilla DOM and hand-written CSS. No framework plugin here,
// and there is not going to be one — see STATE.md, session 12.
export default defineConfig({
  root: "src",
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    target: "safari15",
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
