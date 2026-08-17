import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In local dev, proxy /api to the FastAPI backend so the frontend can
// call relative paths and it "just works" in both dev and prod (prod
// deploys typically put a reverse proxy or the API base URL in an env
// var -- see src/lib/api.js).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
