import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  fullyParallel: false,
  timeout: 90000,
  use: {
    baseURL: process.env.DASHBOARD_URL || "http://127.0.0.1:3000",
    headless: true,
    channel:
      process.env.PLAYWRIGHT_BROWSER === "chromium" ? undefined : "msedge",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
