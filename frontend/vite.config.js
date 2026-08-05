import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api → FastAPI so the browser makes same-origin
// requests and cookies/session work without CORS headaches.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
