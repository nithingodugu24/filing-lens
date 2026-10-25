import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  workers: 1,
  use: {
    baseURL: process.env.DEMO_URL || "http://127.0.0.1:5173",
    headless: true,
    viewport: { width: 1440, height: 1050 },
    screenshot: "only-on-failure",
  },
  reporter: [["list"], ["json", { outputFile: "test-results/results.json" }]],
});
