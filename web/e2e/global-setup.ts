import { execFileSync } from "node:child_process";
import path from "node:path";

import { E2E_ATHLETE_ID } from "../playwright.config";

/** Create the throwaway test athlete and write the search fixture (RaceBest data only). */
export default function globalSetup() {
  const repoRoot = path.resolve(__dirname, "../..");
  execFileSync(
    "uv",
    ["run", "python", "-m", "chipt.db.e2e_fixture", "setup", "--athlete-id", E2E_ATHLETE_ID, "--out", "web/e2e/.fixture.json"],
    { cwd: repoRoot, stdio: "inherit" },
  );
}
