import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Locator, type Page } from "@playwright/test";

const GENERATED = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../backend/data_gen/generated");

const PRIVILEGED_ROLES = new Set([
  "trade_supervisor",
  "journal_approver",
  "payment_approver",
  "access_approver",
  "release_manager",
]);
const CRITICAL_SYSTEMS = new Set(["payments", "general ledger"]);

export function groundTruth(): Record<string, string[]> {
  return JSON.parse(fs.readFileSync(path.join(GENERATED, "ground_truth.json"), "utf8")) as Record<string, string[]>;
}

export function priorityActiveAccountIds(): Set<string> {
  const lines = fs.readFileSync(path.join(GENERATED, "iam_accounts.csv"), "utf8").trim().split("\n");
  const header = lines[0].split(",");
  const idIndex = header.indexOf("account_id");
  const roleIndex = header.indexOf("role");
  const systemIndex = header.indexOf("system");
  const statusIndex = header.indexOf("status");
  const ids = new Set<string>();
  for (const line of lines.slice(1)) {
    const cells = line.split(",");
    if (cells[statusIndex] !== "active") {
      continue;
    }
    if (PRIVILEGED_ROLES.has(cells[roleIndex]) || CRITICAL_SYSTEMS.has(cells[systemIndex])) {
      ids.add(cells[idIndex]);
    }
  }
  return ids;
}

export function activeAccountCount(): number {
  const lines = fs.readFileSync(path.join(GENERATED, "iam_accounts.csv"), "utf8").trim().split("\n");
  const statusIndex = lines[0].split(",").indexOf("status");
  return lines.slice(1).filter((line) => line.split(",")[statusIndex] === "active").length;
}

export async function selectedIds(page: Page): Promise<string[]> {
  const table = page.getByRole("table").filter({ hasText: "Selected ID" });
  const cells = table.locator("tbody tr td:nth-child(2)");
  await expect(cells.first()).toBeVisible();
  return (await cells.allTextContents()).map((value) => value.trim());
}

export async function severityBarValues(panel: Locator): Promise<number[]> {
  const labels = panel.locator(".severity-bar-value");
  await expect(labels).toHaveCount(3);
  const texts = await labels.allTextContents();
  return texts.map((value) => Number(value.trim()));
}

export function sameIds(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((id, index) => id === right[index]);
}
