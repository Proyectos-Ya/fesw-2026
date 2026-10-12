import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "proposal.spec.ts",
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:3108" },
  projects: [
    { name: "desktop" },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: "node node_modules/vite/bin/vite.js --config e2e/proposal.vite.config.ts",
    url: "http://127.0.0.1:3108",
    timeout: 60000,
  },
});
