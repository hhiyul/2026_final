import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const target =
    env.VITE_API_PROXY_TARGET ||
    env.VITE_API_BASE_URL ||
    "http://localhost:8080";
  const apiPaths = [
    "/auth",
    "/users",
    "/garments",
    "/recommend",
    "/analyze",
    "/health",
    "/ui",
    "/thumbnails",
  ];
  return {
    plugins: [react()],
    server: {
      proxy: Object.fromEntries(
        apiPaths.map((path) => [path, { target, changeOrigin: true }]),
      ),
    },
  };
});
