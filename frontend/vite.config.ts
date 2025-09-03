import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const allowedHostsEnv = (env.VITE_ALLOWED_HOSTS || "").trim();
  const allowedHosts = allowedHostsEnv
    ? (allowedHostsEnv === "*" || allowedHostsEnv.toLowerCase() === "true"
        ? true
        : allowedHostsEnv.split(",").map((h) => h.trim()).filter(Boolean))
    : []; // default

  return ({
    server: {
      host: "::",
      port: 8080,
    },
    preview: {
      allowedHosts,
    },
    plugins: [
      react(),
      mode === 'development' &&
      componentTagger(),
    ].filter(Boolean),
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
  });
});
