import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

/** Written by global-setup: one RaceBest finisher whose name is unique in the database. */
type Fixture = {
  athleteId: number;
  result_id: number;
  name: string;
  event_name: string;
  discipline: string;
  distance_label: string;
};
const fx: Fixture = JSON.parse(readFileSync(path.join(__dirname, ".fixture.json"), "utf8"));

test("find → claim → analyse → unclaim (with undo)", async ({ page }) => {
  await test.step("dashboard starts empty for the fresh test athlete", async () => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Welcome to Chipt" })).toBeVisible();
  });

  await test.step("search by name and claim the result", async () => {
    await page.goto("/find");
    await page.getByLabel("Your name").fill(fx.name);
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page).toHaveURL(/[?&]name=/);
    const mine = page.getByRole("checkbox", { name: `This is me: ${fx.name}, ${fx.event_name}` });
    await expect(mine).toBeVisible();
    await mine.check();
    await expect(page.getByRole("region", { name: "Unsaved changes" })).toContainText("1 to add");
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByText("Claimed 1 result.")).toBeVisible();
    await expect(mine).toBeChecked();
  });

  await test.step("my results lists it and the detail page shows field sizes", async () => {
    await page.goto("/results");
    const link = page.getByRole("link", { name: fx.event_name }).first();
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL(new RegExp(`/results/${fx.result_id}$`));
    await expect(page.getByRole("heading", { level: 1, name: fx.event_name })).toBeVisible();
    await expect(page.getByText(/ of \d+/).first()).toBeVisible(); // "Nth of M"
    await expect(page.getByRole("button", { name: /Yours/ })).toBeVisible();
  });

  await test.step("analysis shows the comparison group and the race as PB", async () => {
    await page.getByRole("link", { name: "Compare" }).click();
    await expect(page).toHaveURL(/\/analysis\?/);
    await expect(page.getByRole("combobox")).toContainText(fx.distance_label);
    await expect(page.getByText("Personal best")).toBeVisible();
    const row = page.getByRole("row", { name: new RegExp(fx.event_name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) });
    await expect(row).toContainText("PB");
  });

  await test.step("dashboard shows a PB card for the group", async () => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Personal bests" })).toBeVisible();
    await expect(page.getByRole("link", { name: new RegExp(fx.distance_label) }).first()).toBeVisible();
  });

  await test.step("remove from my results, undo, then remove for good", async () => {
    await page.goto("/results");
    const remove = page.getByRole("button", { name: `Remove ${fx.event_name} from your results` });
    await remove.click();
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(page.getByRole("link", { name: fx.event_name }).first()).toBeVisible();
    await remove.click();
    await expect(page.getByRole("heading", { name: "No results claimed yet" })).toBeVisible();
  });
});
