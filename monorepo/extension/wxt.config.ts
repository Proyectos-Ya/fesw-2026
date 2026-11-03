import { defineConfig } from "wxt";
import { buildManifest } from "./src/config/manifest";

export default defineConfig({
  srcDir: "src",
  manifest: (env) => buildManifest({ mode: env.mode, browser: env.browser }),
});
