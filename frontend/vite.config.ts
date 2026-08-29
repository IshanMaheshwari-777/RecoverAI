import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// By default the build lands directly in the Python package so
// `recover-ai serve` (FastAPI) can host it with zero extra steps. Set
// VITE_OUT_DIR=dist when building on a static host like Vercel.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: process.env.VITE_OUT_DIR ?? "../src/recover_ai/api/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
