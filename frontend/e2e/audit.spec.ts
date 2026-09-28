import fs from "node:fs";
import { expect, test } from "@playwright/test";
import { activeAccountCount, groundTruth, priorityActiveAccountIds, sameIds, selectedIds, severityBarValues } from "./helpers";

test.describe.configure({ mode: "serial" });

test("data page shows the seeded row counts", async ({ page }) => {
  await page.goto("/data");
  const table = page.getByRole("table").filter({ has: page.getByRole("columnheader", { name: "Rows" }) });
  await expect(table.getByRole("row", { name: /HR roster/ })).toContainText("400");
  await expect(table.getByRole("row", { name: /Role permissions/ })).toContainText("15");
  await expect(table.getByRole("row", { name: /Segregation-of-duties rules/ })).toContainText("5");
  await expect(table.getByRole("row", { name: /IAM accounts/ })).toContainText("811");
  await expect(table.getByRole("row", { name: /Change tickets/ })).toContainText("50");
});

test("running all five controls matches ground truth and the severity chart", async ({ page }) => {
  const truth = groundTruth();
  expect(Object.keys(truth).sort()).toEqual(["ITGC-01", "ITGC-02", "ITGC-03", "ITGC-04", "ITGC-05"]);
  const expected = Object.fromEntries(Object.entries(truth).map(([controlId, ids]) => [controlId, ids.length]));
  expect(expected).toEqual({
    "ITGC-01": 8,
    "ITGC-02": 6,
    "ITGC-03": 10,
    "ITGC-04": 6,
    "ITGC-05": 5,
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Controls tested" }).locator("xpath=..")).toContainText("0 of 6");
  await expect(page.getByText("No workpapers yet. Open a test to draft one.")).toBeVisible();

  await page.getByRole("button", { name: "Run all tests" }).click();
  await expect(page.getByRole("button", { name: "Run all tests" })).toBeEnabled({ timeout: 60_000 });

  const table = page.getByRole("table").first();
  let sum = 0;
  for (const [controlId, count] of Object.entries(expected)) {
    const row = table.getByRole("row", { name: new RegExp(controlId) });
    await expect(row).toContainText(String(count));
    sum += count;
  }
  await expect(table.getByRole("row", { name: /ITGC-06/ })).toContainText("0");

  const totalCard = page.locator("article", { has: page.getByRole("heading", { name: "Total exceptions" }) });
  await expect(totalCard.locator(".stat-value")).toHaveText(String(sum));

  const severity = page.locator("section", { has: page.getByRole("heading", { name: "Exceptions by severity" }) });
  const bars = await severityBarValues(severity);
  expect(bars.reduce((total, value) => total + value, 0)).toBe(sum);

  const runs = await page.request.get("/api/tests");
  expect(runs.ok()).toBeTruthy();
  const body = (await runs.json()) as { runs: Array<{ exceptions: Array<{ severity: string }> }> };
  const fromApi = { high: 0, medium: 0, low: 0 };
  for (const run of body.runs) {
    for (const row of run.exceptions) {
      fromApi[row.severity as "high" | "medium" | "low"] += 1;
    }
  }
  expect(bars).toEqual([fromApi.high, fromApi.medium, fromApi.low]);
  expect(fromApi.high + fromApi.medium + fromApi.low).toBe(sum);

  for (const [controlId, count] of Object.entries(expected)) {
    await page.goto(`/tests/${controlId}`);
    await expect(page.getByText(`Exceptions ${count}.`)).toBeVisible();
    if (count > 0) {
      await expect(page.getByText(`Showing ${count} of ${count}`)).toBeVisible();
    }
  }
});

test("a fixed seed repeats a sample and risk-based selection starts with higher-risk items", async ({ page }) => {
  await page.goto("/tests/ITGC-04");
  await page.getByLabel("Sample size").fill("5");
  await page.getByLabel("Seed").fill("42");
  await drawSample(page);
  const first = await selectedIds(page);
  expect(first).toHaveLength(5);

  await page.getByLabel("Seed").fill("99");
  await drawSample(page);
  await expect.poll(async () => sameIds(await selectedIds(page), first)).toBeFalsy();
  const other = await selectedIds(page);
  expect(other).toHaveLength(5);

  await page.getByLabel("Seed").fill("42");
  await drawSample(page);
  await expect.poll(async () => selectedIds(page)).toEqual(first);

  const priority = priorityActiveAccountIds();
  const population = activeAccountCount();
  expect(priority.size).toBeGreaterThan(0);
  expect(priority.size).toBeLessThan(population);
  const sampleSize = priority.size + 1;
  await page.getByLabel("Method").selectOption("risk_based");
  await page.getByLabel("Sample size").fill(String(sampleSize));
  await page.getByLabel("Seed").fill("7");
  await drawSample(page);
  await expect.poll(async () => (await selectedIds(page)).length).toBe(sampleSize);
  const riskBased = await selectedIds(page);
  expect(riskBased).toHaveLength(sampleSize);
  for (const id of riskBased.slice(0, priority.size)) {
    expect(priority.has(id)).toBeTruthy();
  }
  expect(priority.has(riskBased[priority.size])).toBeFalsy();
});

test("an ITGC-01 workpaper can be edited, approved, and exported", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/tests/ITGC-01");
  await page.getByRole("button", { name: "Generate workpaper" }).click();
  await page.waitForURL(/\/workpapers\/\d+$/, { timeout: 150_000 });

  const sections = [
    "Control objective",
    "Risk addressed",
    "Procedure performed",
    "Population and sample",
    "Results",
    "Exceptions noted",
    "Conclusion",
  ];
  for (const name of sections) {
    await expect(page.getByRole("textbox", { name })).not.toHaveValue("");
  }

  const population = page.getByRole("textbox", { name: "Population and sample" });
  await expect(population).not.toHaveValue(/\bactive\b/i);
  await expect(population).toHaveValue(/Records loaded:/);
  await expect(population).toHaveValue(/Records tested:/);
  await expect(population).toHaveValue(/Records excluded:/);

  const procedure = page.getByRole("textbox", { name: "Procedure performed" });
  const edited = `${await procedure.inputValue()} Reviewed for completeness and accuracy.`;
  await procedure.fill(edited);
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();
  await expect(procedure).toHaveValue(edited);

  await page.getByRole("button", { name: "Mark reviewed" }).click();
  await expect(page.getByText("Marked reviewed.")).toBeVisible();
  await expect(page.locator(".badge")).toHaveText("reviewed");

  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("This workpaper is approved and read-only.")).toBeVisible();
  await expect(procedure).toHaveAttribute("readonly", "");
  await expect(page.getByRole("button", { name: "Save" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Approve" })).toBeDisabled();

  const id = page.url().match(/\/workpapers\/(\d+)$/)?.[1];
  expect(id).toBeTruthy();
  const rejected = await page.request.patch(`/api/workpapers/${id}`, {
    data: { reviewer_notes: "Change after approval." },
  });
  expect(rejected.status()).toBe(400);
  expect(await rejected.json()).toMatchObject({ detail: expect.stringMatching(/read-only/i) });

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export markdown" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("ITGC-01");
  const exported = await download.path();
  expect(exported).toBeTruthy();
  const markdown = fs.readFileSync(exported as string, "utf8");
  expect(markdown).toContain("ITGC-01");
  expect(markdown).toContain("Reviewed for completeness and accuracy.");
});

async function drawSample(page: import("@playwright/test").Page): Promise<void> {
  const response = page.waitForResponse(
    (result) => result.url().includes("/sample") && result.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Generate sample" }).click();
  expect((await response).ok()).toBeTruthy();
}

test("a malformed CSV shows an error and leaves the seeded count in place", async ({ page }) => {
  await page.goto("/data");
  await page.getByLabel("CSV for HR roster").setInputFiles({
    name: "broken.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("employee_id,name\nE9999,Broken Row\n", "utf8"),
  });
  const roster = page.getByRole("row", { name: /HR roster/ });
  await roster.getByRole("button", { name: "Upload" }).click();
  const alert = page.getByRole("alert");
  await expect(alert).toBeVisible();
  await expect(alert).toContainText("columns");
  await expect(roster).toContainText("400");
  await expect(page.getByRole("heading", { name: "Data", exact: true })).toBeVisible();
});

test("laptop width keeps the overview usable", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 800 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expectNoPageOverflow(page);

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/tests/ITGC-03");
  await expect(page.getByText("Showing 10 of 10")).toBeVisible();
  await expectNoPageOverflow(page);
});

async function expectNoPageOverflow(page: import("@playwright/test").Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(overflow).toBeFalsy();
}
