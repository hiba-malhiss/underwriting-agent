import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const BACKEND = "http://127.0.0.1:8001";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // "@/components/ui/button" → src/components/ui/button (the alias shadcn/ui generates for)
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  server: {
    port: 5174, // 5173 is the Amazon agent's
    // Only API paths: they must not match a page path, or a refresh there would hit the backend
    proxy: {
      "/documents": BACKEND,
      "/rules": BACKEND,
      "/health": BACKEND,
    },
  },
});
