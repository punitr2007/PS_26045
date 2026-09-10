import { defineConfig, loadEnv } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig(async ({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendTarget =
    env.VITE_BACKEND_URL || process.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

  const plugins = [
    tailwindcss(),
    tanstackStart({
      server: { entry: "server" },
    }),
    viteReact(),
  ];

  if (command === "build") {
    const { nitro } = await import("nitro/vite");
    plugins.push(nitro());
  }

  return {
    resolve: {
      tsconfigPaths: true,
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
      dedupe: [
        "react",
        "react-dom",
        "react/jsx-runtime",
        "react/jsx-dev-runtime",
        "@tanstack/react-query",
        "@tanstack/query-core",
      ],
    },
    plugins,
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
