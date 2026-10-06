// Two declared projects; only Chromium is installed in CI. WebKit is deliberately not configured.
const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests",
  retries: 1,
  use: { screenshot: "only-on-failure", trace: "on-first-retry" },
  projects: [
    // ASSERTIVA_PW_CHANNEL lets a machine that cannot download browsers use an installed Chromium build (e.g. msedge).
    { name: "chromium", use: { ...devices["Desktop Chrome"], channel: process.env.ASSERTIVA_PW_CHANNEL || undefined } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
  ],
});
