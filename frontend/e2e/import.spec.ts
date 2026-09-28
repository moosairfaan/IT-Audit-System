import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const fixtures = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../backend/tests/fixtures/import");

test("the import wizard reports skips and company data can be switched off", async ({ page }) => {
  await page.goto("/import");
  await expect(page.getByRole("heading", { name: "Import company data" })).toBeVisible();

  await page.getByLabel("HR roster file").setInputFiles(path.join(fixtures, "hr_roster.csv"));
  await page.getByLabel("IAM accounts file").setInputFiles(path.join(fixtures, "iam_accounts.csv"));
  await page.getByLabel("Role permissions file").setInputFiles(path.join(fixtures, "role_permissions.csv"));
  await page.getByLabel("Change tickets file").setInputFiles(path.join(fixtures, "change_tickets.csv"));
  const uploadContinue = page.getByRole("button", { name: "Continue" });
  await expect(uploadContinue).toBeEnabled();
  await uploadContinue.click();

  await expect(page.getByLabel("Column for employee id on HR roster")).toHaveValue("Emp ID");
  await expect(page.getByLabel("Column for account id on IAM accounts")).toHaveValue("Account Number");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByRole("heading", { name: "Value normalization" })).toBeVisible();
  await expect(page.getByLabel("Status for Active", { exact: true })).toHaveValue("active");
  await expect(page.getByLabel("Status for A", { exact: true })).toHaveValue("active");
  await expect(page.getByLabel("Status for Enabled", { exact: true })).toHaveValue("active");
  await expect(page.getByLabel("Status for 1", { exact: true })).toHaveValue("active");
  await expect(page.getByLabel("Status for NotAStatus", { exact: true })).toHaveValue("");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByRole("heading", { name: "Validation report" })).toBeVisible();
  const roster = page.getByRole("row", { name: /HR roster/ });
  await expect(roster).toContainText("6");
  await expect(roster).toContainText("3");
  await expect(page.getByText("missing employee_id")).toBeVisible();
  await expect(page.getByText("bad date in hire_date")).toBeVisible();
  await expect(page.getByText("duplicate employee_id")).toBeVisible();
  await expect(page.getByText("status value has no mapping")).toBeVisible();
  const accounts = page.getByRole("row", { name: /IAM accounts/ });
  await expect(accounts).toContainText("4");

  await page.getByRole("button", { name: "Import company data" }).click();
  await expect(page.getByText("Company data is now the active source.")).toBeVisible();
  await expect(page.getByText("Company data is active. Controls are reading the uploaded files.")).toBeVisible();

  await page.goto("/data");
  await page.getByRole("button", { name: "Demo data" }).click();
  await expect(page.getByRole("row", { name: /HR roster/ })).toContainText("400");
  await expect(page.getByText("Company data is active. Controls are reading the uploaded files.")).toHaveCount(0);
});
