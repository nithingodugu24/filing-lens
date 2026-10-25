import { test, expect } from "@playwright/test";

test("first-time screen explains the steps and offers sample reports", async ({
  page,
}) => {
  await page.route("**/api/documents", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: (await response.json()).filter(
        (d: { synthetic: boolean }) => d.synthetic,
      ),
    });
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "Start with a company report",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Upload your first report", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Try with sample reports", exact: true })
    .click();
  await expect(
    page.getByText("4 sample reports ready", { exact: true }),
  ).toBeVisible();
});

test("failed upload has a clear next step instead of a silent disabled form", async ({
  page,
}) => {
  await page.route("**/api/documents", (route) =>
    route.fulfill({
      json: [
        {
          id: "failed-doc",
          company: "Test",
          title: "Failed test PDF",
          synthetic: false,
          status: "failed",
          warning: "Scanned PDF: no reliable text.",
          document_type: "annual_report",
          period_start: "2025-04-01",
          period_end: "2026-03-31",
          page_count: 0,
          job: null,
        },
      ],
    }),
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Your report needs attention" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "View report status", exact: true })
    .click();
  await expect(
    page.getByText("Scanned PDF: no reliable text.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Retry", exact: true }),
  ).toBeVisible();
});
async function samples(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByLabel("Reports to use").selectOption("samples");
  await expect(
    page.getByText("4 sample reports ready", { exact: true }),
  ).toBeVisible();
}
test("simple question, source reader and PDF page", async ({ page }) => {
  await samples(page);
  await page.screenshot({
    path: "../docs/screenshots/research-desk.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Compare revenue growth", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Results from your reports" }),
  ).toBeVisible();
  await expect(
    page.locator(".calculation-result").filter({ hasText: "2.5" }),
  ).toBeVisible();
  await expect(
    page.locator(".calculation-result").filter({ hasText: "4" }),
  ).toBeVisible();
  await page.locator(".citation").first().click();
  const reader = page.getByRole("dialog", { name: "Evidence reader" });
  await expect(reader.getByText("Tables found on this page")).toBeVisible();
  await expect(reader.getByRole("link", { name: "Open PDF" })).toHaveAttribute(
    "href",
    /#page=1$/,
  );
  await reader.getByRole("button", { name: "View PDF" }).click();
  await expect(reader.locator("iframe")).toHaveAttribute("src", /#page=1$/);
  await page.keyboard.press("Escape");
  await expect(reader).not.toBeVisible();
});
test("filters clear old results and unsupported question is clear", async ({
  page,
}) => {
  await samples(page);
  await page.getByLabel("Company filter").selectOption("TCS");
  await page.getByLabel("Period filter").selectOption("2025-09-30");
  await expect(
    page.getByText("1 sample report ready", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Your question").fill("What is the share price?");
  await page.getByRole("button", { name: "Find answer", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "This is not in these reports" }),
  ).toBeVisible();
  await page.getByLabel("Period filter").selectOption("all");
  await expect(
    page.getByRole("heading", { name: "This is not in these reports" }),
  ).not.toBeVisible();
});
test("comparison shows source values and basis points", async ({ page }) => {
  await samples(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Compare numbers", exact: true })
    .click();
  await page.getByLabel("Company filter").selectOption("TCS");
  await page.getByLabel("Comparison metric").selectOption("operating_margin");
  await page.getByLabel("Calculation type").selectOption("basis_points");
  await page
    .locator(".compare-builder")
    .getByRole("button", { name: "Compare numbers", exact: true })
    .click();
  await expect(page.locator(".calculation-result")).toHaveText(
    "100basis points",
  );
  await expect(page.locator(".calculation-inputs")).toContainText("24 percent");
  await expect(page.locator(".calculation-inputs")).toContainText("25 percent");
});
test("reports, keyboard-friendly upload and mobile navigation", async ({
  page,
}) => {
  await samples(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "My reports", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Open TCS Q2 FY26 · Synthetic results" })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Evidence reader" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Upload report", exact: true })
    .click();
  const upload = page.getByRole("dialog", { name: "Upload report" });
  await expect(upload).toBeVisible();
  await expect(
    upload.getByRole("button", { name: "Upload report", exact: true }),
  ).toBeDisabled();
  await expect(
    upload.getByRole("button", { name: "Close upload" }),
  ).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(
    upload.getByRole("button", { name: "Cancel", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Ask a question", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Ask questions about company reports" }),
  ).toBeVisible();
  for (const name of ["Ask a question", "My reports", "Compare numbers"])
    await expect(
      page.getByRole("navigation").getByRole("button", { name, exact: true }),
    ).toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../docs/screenshots/research-mobile.png",
    fullPage: true,
  });
});
test("sample data and uploaded reports are kept separate in questions", async ({
  page,
}) => {
  const fixtureDoc = {
    id: "user-doc",
    company: "Example Ltd",
    title: "Uploaded annual report",
    document_type: "annual_report",
    period_start: "2025-04-01",
    period_end: "2026-03-31",
    publication_date: null,
    source_url: null,
    currency: "INR",
    units: null,
    basis: "consolidated",
    synthetic: false,
    status: "indexed",
    warning: null,
    page_count: 2,
    job: null,
  };
  await page.route("**/api/documents", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: [...(await response.json()), fixtureDoc],
    });
  });
  const filters: boolean[] = [];
  await page.route("**/api/questions", async (route) => {
    filters.push(route.request().postDataJSON().filters.synthetic);
    await route.fulfill({
      json: {
        abstained: true,
        claims: [],
        evidence: [],
        calculations: [],
        limitation: "No matching evidence.",
        configuration: {},
        usage: {},
      },
    });
  });
  await page.goto("/");
  await expect(page.getByText("1 report ready", { exact: true })).toBeVisible();
  await page.getByLabel("Your question").fill("Revenue details");
  await page.getByRole("button", { name: "Find answer", exact: true }).click();
  await expect(
    page.getByText("No matching evidence.", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Reports to use").selectOption("samples");
  await page.getByRole("button", { name: "Find answer", exact: true }).click();
  await expect(
    page.getByText("No matching evidence.", { exact: true }),
  ).toBeVisible();
  expect(filters).toEqual([false, true]);
});
