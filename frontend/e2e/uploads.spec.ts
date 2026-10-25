import { test, expect } from "@playwright/test";

async function openUpload(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.getByText("4 indexed & searchable")).toBeVisible();
  await page.getByRole("button", { name: "Add document", exact: true }).click();
}

test("PDF above the old 20 MB limit reaches the upload endpoint", async ({
  page,
}) => {
  let uploadedBytes = 0;
  await page.route("**/api/documents", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    uploadedBytes = route.request().postDataBuffer()?.byteLength || 0;
    await route.fulfill({ status: 202, json: { duplicate: false } });
  });
  await openUpload(page);
  await expect(
    page.getByText("PDF only · Up to 100 MB · No scanned documents"),
  ).toBeVisible();
  const bytes = Buffer.alloc(21 * 1024 * 1024, 32);
  bytes.write("%PDF-1.7\n");
  await page
    .getByLabel("PDF file")
    .setInputFiles({
      name: "large-annual-report.pdf",
      mimeType: "application/pdf",
      buffer: bytes,
    });
  await page.getByLabel("Company name", { exact: true }).fill("Upload test");
  await page
    .getByLabel("Document title", { exact: true })
    .fill("Synthetic upload validation");
  await page.getByLabel("Period start", { exact: true }).fill("2025-04-01");
  await page.getByLabel("Period end", { exact: true }).fill("2026-03-31");
  await page
    .getByRole("button", { name: "Upload & process", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Add a document" }),
  ).not.toBeVisible();
  expect(uploadedBytes).toBeGreaterThan(21 * 1024 * 1024);
});

test("configured limit is used immediately when selecting a file", async ({
  page,
}) => {
  await page.route("**/api/ready", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: { ...(await response.json()), max_upload_mb: 1 },
    });
  });
  await openUpload(page);
  await page
    .getByLabel("PDF file")
    .setInputFiles({
      name: "too-large.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.alloc(2 * 1024 * 1024),
    });
  await expect(page.getByRole("alert")).toHaveText(
    "This PDF is 2.0 MB. The upload limit is 1 MB.",
  );
  await expect(
    page.getByRole("button", { name: "Upload & process", exact: true }),
  ).toBeDisabled();
  await page.screenshot({
    path: "../docs/screenshots/upload-size-validation.png",
    fullPage: true,
  });
});
