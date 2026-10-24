import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const endpoints = [
  "/auth",
  "/salud",
  "/lotes",
  "/trabajos",
  "/datos",
  "/modelo",
  "/auditoria",
  "/reportes",
  "/observaciones",
  "/documentos",
  "/mantenimiento",
  "/metricas",
  "/usuarios",
  "/api",
  "/gastos",
  "/docs",
  "/openapi.json",
  "/redoc",
];

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: Object.fromEntries(
      endpoints.map((path) => [path, { target: "http://127.0.0.1:8000" }]),
    ),
  },
  preview: {
    proxy: Object.fromEntries(
      endpoints.map((path) => [path, { target: "http://127.0.0.1:8000" }]),
    ),
  },
  build: { sourcemap: false },
});
