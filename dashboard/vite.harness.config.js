// Harness-only build. Keeps the audit entry point out of the app bundle.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "harness",
  base: "./",
  plugins: [react()],
  build: { outDir: "../.harness-dist", emptyOutDir: true, sourcemap: false },
});
