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
        // Keep the original Host header so the backend builds its OAuth
        // callback as localhost:5173 (this origin) rather than :8000. That
        // keeps the whole login round-trip on one origin, so the session
        // cookie is set where the app can actually read it.
        changeOrigin: false,
      },
    },
  },
});
