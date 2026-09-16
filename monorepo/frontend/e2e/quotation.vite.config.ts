import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  root: path.resolve(__dirname, "quotation-fixture"),
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "../src") } },
  server: { host: "127.0.0.1", port: 3107, strictPort: true },
});
