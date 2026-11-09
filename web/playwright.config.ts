import { defineConfig, devices } from "@playwright/test";

/*
 * Smoke tests for the core flow: Find → Claim → Analyse → Unclaim.
 *
 * They run against the REAL local Postgres (docker compose up -d), but as a dedicated,
 * throwaway test athlete (E2E_ATHLETE_ID), never the real one: global-setup creates it and
 * global-teardown deletes it with its claims. The API and web app run on their own ports
 * (8010 / 3010) so they don't collide with your dev servers on 8000 / 3000.
 */
export const E2E_ATHLETE_ID = process.env.E2E_ATHLETE_ID ?? "900";
const API_PORT = 8010;
const WEB_PORT = 3010;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1, // one test athlete, shared state: run serially
  retries: 0,
  reporter: [["list"]],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      // Run from the repo root so the API reads the root .env (DATABASE_URL etc.).
      command: `uv run uvicorn chipt.api.main:app --app-dir src --port ${API_PORT}`,
      cwd: "..",
      url: `http://127.0.0.1:${API_PORT}/health`,
      env: {
        DEFAULT_ATHLETE_ID: E2E_ATHLETE_ID,
        CORS_ALLOWED_ORIGINS: `http://localhost:${WEB_PORT}`,
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx next dev --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      env: {
        NEXT_PUBLIC_API_BASE_URL: `http://127.0.0.1:${API_PORT}`,
        NEXT_DIST_DIR: ".next-e2e",
      },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
