import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 同域路径部署：VITE_BASE=/pmo/ npm run build
const base = process.env.VITE_BASE || "/";

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
