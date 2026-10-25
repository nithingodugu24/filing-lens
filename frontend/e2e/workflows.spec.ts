import { test, expect } from "@playwright/test";
test("question, evidence reader and PDF page", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("4 indexed & searchable")).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/research-desk.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: /Put growth in context/ }).click();
  await expect(
    page.getByRole("heading", { name: "From the disclosures" }),
  ).toBeVisible();
  await expect(
    page.locator(".calculation-result").filter({ hasText: "2.5" }),
  ).toBeVisible();
  await expect(
    page.locator(".calculation-result").filter({ hasText: "4" }),
  ).toBeVisible();
  await page.locator(".citation").first().click();
  const reader = page.getByRole("dialog", { name: "Evidence reader" });
  await expect(reader).toBeVisible();
  await expect(reader.getByText("Extracted tables")).toBeVisible();
  await expect(reader.locator("a", { hasText: "Open PDF" })).toHaveAttribute(
    "href",
    /#page=1$/,
  );
  await reader.getByRole("button", { name: "PDF preview" }).click();
  await expect(reader.locator("iframe")).toHaveAttribute("src", /#page=1$/);
  await reader.getByRole("button", { name: "Close evidence reader" }).click();
  await expect(reader).not.toBeVisible();
});
test("metadata filters and unsupported question", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Company filter", { exact: true }).selectOption("TCS");
  await page
    .getByLabel("Period filter", { exact: true })
    .selectOption("2025-09-30");
  await expect(page.getByText("1 documents in scope")).toBeVisible();
  await page
    .getByLabel("Your question", { exact: true })
    .fill("What is the share price?");
  await page
    .getByRole("button", { name: "Ask FilingLens", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "More evidence needed" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Insufficient evidence in the selected disclosures/),
  ).toBeVisible();
});
test("comparison checks inputs and basis points", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Compare metrics", exact: true })
    .click();
  await page.getByLabel("Company filter", { exact: true }).selectOption("TCS");
  await page.getByLabel("Comparison metric").selectOption("operating_margin");
  await page.getByLabel("Calculation type").selectOption("basis_points");
  await page.getByRole("button", { name: "Calculate comparison" }).click();
  await expect(page.locator(".calculation-result")).toHaveText(
    "100basis points",
  );
  await expect(page.locator(".calculation-inputs")).toContainText("24 percent");
  await expect(page.locator(".calculation-inputs")).toContainText("25 percent");
});
test("library preview, upload validation and responsive layout", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Document library/ }).click();
  await page
    .getByRole("button", { name: "Open TCS Q2 FY26 · Synthetic results" })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Evidence reader" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close evidence reader" }).click();
  await page.getByRole("button", { name: "Add document", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Add a document" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Upload & process" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "The source of every insight." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page
    .getByRole("button", { name: "Research desk", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Your research, grounded." }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/research-mobile.png",
    fullPage: true,
  });
});
