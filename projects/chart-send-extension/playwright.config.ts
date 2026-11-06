import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  fullyParallel: false,
  timeout: 60000,
  retries: 0,
  reporter: "list",
  use: { trace: "off" },
  outputDir: "test-results",
});
