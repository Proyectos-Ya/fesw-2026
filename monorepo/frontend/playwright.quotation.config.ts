import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "quotation.spec.ts",
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:3107" },
  projects: [
    { name: "desktop" },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: "node node_modules/vite/bin/vite.js --config e2e/quotation.vite.config.ts",
    url: "http://127.0.0.1:3107", timeout: 60000,
  },
});
