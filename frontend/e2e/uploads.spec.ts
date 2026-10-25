import { test, expect } from "@playwright/test";
async function openUpload(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Upload report", exact: true })
    .click();
}
test("large annual report upload uses sensible dates and fewer fields", async ({
  page,
}) => {
  let uploadedBytes = 0,
    metadata: Record<string, unknown> = {};
  await page.route("**/api/documents", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const buffer = route.request().postDataBuffer()!;
    uploadedBytes = buffer.length;
    const match = buffer.toString().match(/name="metadata"\r\n\r\n([^\r]+)/);
    metadata = JSON.parse(match![1]);
    await route.fulfill({
      status: 202,
      json: {
        duplicate: false,
        document: { company: "Upload test", synthetic: false },
      },
    });
  });
  await openUpload(page);
  const dialog = page.getByRole("dialog", { name: "Upload report" });
  const bytes = Buffer.alloc(21 * 1024 * 1024, 32);
  bytes.write("%PDF-1.7\n");
  await dialog.getByLabel("PDF file").setInputFiles({
    name: "annual-report-2025-2026.pdf",
    mimeType: "application/pdf",
    buffer: bytes,
  });
  await dialog.getByLabel("Company name", { exact: true }).fill("Upload test");
  await expect(
    dialog.getByText("1 Apr 2025 – 31 Mar 2026", { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByLabel("Report name", { exact: true }),
  ).not.toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/upload-simple.png",
    fullPage: true,
  });
  await dialog
    .getByRole("button", { name: "Upload report", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  expect(uploadedBytes).toBeGreaterThan(21 * 1024 * 1024);
  expect(metadata).toMatchObject({
    company: "Upload test",
    document_type: "annual_report",
    period_start: "2025-04-01",
    period_end: "2026-03-31",
    title: "annual report 2025 2026",
    units: null,
  });
});
test("configured limit gives immediate feedback", async ({ page }) => {
  await page.route("**/api/ready", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: { ...(await response.json()), max_upload_mb: 1 },
    });
  });
  await openUpload(page);
  const dialog = page.getByRole("dialog", { name: "Upload report" });
  await expect(
    dialog.getByText("PDF files up to 1 MB", { exact: true }),
  ).toBeVisible();
  await dialog.getByLabel("PDF file").setInputFiles({
    name: "too-large.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.alloc(2 * 1024 * 1024),
  });
  await expect(dialog.getByRole("alert")).toContainText(
    "This PDF is 2.0 MB. The upload limit is 1 MB.",
  );
  await expect(
    dialog.getByRole("button", { name: "Upload report", exact: true }),
  ).toBeDisabled();
  await page.screenshot({
    path: "../docs/screenshots/upload-size-validation.png",
    fullPage: true,
  });
});
test("quarterly dates and custom dates can both be selected", async ({
  page,
}) => {
  await openUpload(page);
  const dialog = page.getByRole("dialog", { name: "Upload report" });
  await dialog
    .getByLabel("Financial year", { exact: true })
    .selectOption("2025");
  await dialog
    .getByLabel("Report type", { exact: true })
    .selectOption("quarterly_results");
  await dialog.getByLabel("Quarter", { exact: true }).selectOption("Q4");
  await expect(
    dialog.getByText("1 Jan 2026 – 31 Mar 2026", { exact: true }),
  ).toBeVisible();
  await dialog.getByLabel("Use different dates").check();
  await dialog.getByLabel("Period start", { exact: true }).fill("2025-01-01");
  await dialog.getByLabel("Period end", { exact: true }).fill("2025-12-31");
  await expect(
    dialog.getByText("1 Jan 2025 – 31 Dec 2025", { exact: true }),
  ).toBeVisible();
});
