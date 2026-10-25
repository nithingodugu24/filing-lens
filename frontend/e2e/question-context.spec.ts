import { test, expect } from "@playwright/test";

async function selectedSample(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Ask a question", exact: true })
    .click();
  await page.getByLabel("Reports to use").selectOption("samples");
  await page.getByLabel("Company filter").selectOption("TCS");
  await page.getByLabel("Period filter").selectOption("2025-09-30");
  await expect(
    page.getByText("1 sample report ready", { exact: true }),
  ).toBeVisible();
}

test("what is this explains the selected report and links to its opening page", async ({
  page,
}) => {
  await selectedSample(page);
  await page.getByLabel("Your question").fill("what is this?");
  await page.getByRole("button", { name: "Find answer", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "About this report", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".reply-summary")).toContainText(
    "TCS's quarterly results",
  );
  await expect(page.locator(".reply-summary")).toContainText("2 pages");
  await expect(page.locator(".reply-summary")).toContainText("made-up sample");
  await page
    .locator(".report-overview")
    .getByRole("button", { name: "Open report · page 1", exact: true })
    .click();
  const reader = page.getByRole("dialog", { name: "Evidence reader" });
  await expect(reader.locator(".reader-text")).toContainText("SYNTHETIC DEMO");
  await expect(reader.getByRole("link", { name: "Open PDF" })).toHaveAttribute(
    "href",
    /#page=1$/,
  );
  await page.keyboard.press("Escape");
  await page
    .locator(".answer-suggestions")
    .getByRole("button", {
      name: "What did management say about operating margin?",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Results from your reports",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.locator(".claim").filter({ hasText: "utilisation" }),
  ).toBeVisible();
});

test("vague questions ask for clarification and offer a working next step", async ({
  page,
}) => {
  await selectedSample(page);
  await page.getByLabel("Your question").fill("why?");
  await page.getByRole("button", { name: "Find answer", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "What would you like to understand?",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator(".reply-summary")).toContainText(
    "specific financial figure",
  );
  await page
    .locator(".answer-suggestions")
    .getByRole("button", { name: "What is this report?", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "About this report", exact: true }),
  ).toBeVisible();
});
