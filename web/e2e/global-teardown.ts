import { execFileSync } from "node:child_process";
import path from "node:path";

import { E2E_ATHLETE_ID } from "../playwright.config";

/** Delete the test athlete (its claims cascade). Never touches the real athlete. */
export default function globalTeardown() {
  const repoRoot = path.resolve(__dirname, "../..");
  execFileSync("uv", ["run", "python", "-m", "chipt.db.e2e_fixture", "teardown", "--athlete-id", E2E_ATHLETE_ID], {
    cwd: repoRoot,
    stdio: "inherit",
  });
}
