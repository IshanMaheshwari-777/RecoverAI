import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The build lands directly in the Python package so `revenue-recovery serve`
// (FastAPI) can host it with zero extra steps.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../src/revenue_recovery/api/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
