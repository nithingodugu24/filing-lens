import { test, expect, type Page } from "@playwright/test";

async function samples(page: Page) {
  await page.goto("/");
  await page.getByLabel("Reports to use").selectOption("samples");
  await expect(
    page.getByText("4 sample reports ready", { exact: true }),
  ).toBeVisible();
}
test("dashboard shows checked trends and respects selected company", async ({
  page,
}) => {
  await samples(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Dashboard", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Revenue over time" }),
  ).toBeVisible();
  await expect(page.locator(".kpi-card").first()).toContainText("4");
  await expect(page.locator(".recharts-line")).toHaveCount(2);
  await page.screenshot({
    path: "../docs/screenshots/dashboard.png",
    fullPage: true,
  });
  await page.getByLabel("Company filter", { exact: true }).selectOption("TCS");
  await expect(page.locator(".kpi-card").first()).toContainText("2");
  await expect(page.locator(".recharts-line")).toHaveCount(1);
});
test("conversation keeps follow-up turns and opens cited pages", async ({
  page,
}) => {
  await samples(page);
  await page
    .getByRole("button", { name: "Conversation mode", exact: true })
    .click();
  await page
    .getByLabel("Ask a follow-up")
    .fill("What affected operating margin?");
  await page
    .getByRole("button", { name: "Send question", exact: true })
    .click();
  await expect(page.locator(".chat-turn")).toHaveCount(1);
  await page.getByLabel("Ask a follow-up").fill("Why did it change?");
  await page
    .getByRole("button", { name: "Send question", exact: true })
    .click();
  await expect(page.locator(".chat-turn")).toHaveCount(2);
  await page.locator(".chat-answer .citation").first().click();
  await expect(
    page
      .getByRole("dialog", { name: "Evidence reader" })
      .locator(".reader-text mark"),
  ).toBeVisible();
});
test("source highlighting, PDF navigation and saved note work together", async ({
  page,
}) => {
  await samples(page);
  const noteText = `Browser test note ${Date.now()}`;
  await page.getByLabel("Company filter", { exact: true }).selectOption("TCS");
  await page.getByLabel("Period filter").selectOption("2025-09-30");
  // Use the labelled question box, independent of example-chip wording.
  const question = page.locator(".question-card textarea");
  await question.fill("What improved utilisation?");
  await page.getByRole("button", { name: "Find answer", exact: true }).click();
  await page
    .locator(".claim")
    .filter({ hasText: "utilisation" })
    .first()
    .locator(".citation")
    .first()
    .click();
  const reader = page.getByRole("dialog", { name: "Evidence reader" });
  await expect(reader.locator(".reader-text mark")).toBeVisible();
  await reader.getByRole("button", { name: "View PDF", exact: true }).click();
  await expect(reader.locator(".react-pdf__Page canvas")).toBeVisible();
  await expect(
    reader.locator(".react-pdf__Page__textContent mark").first(),
  ).toBeVisible();
  await reader.getByRole("button", { name: "Previous", exact: true }).click();
  await expect(reader.getByText("Page 1 / 2", { exact: true })).toBeVisible();
  await reader.getByRole("button", { name: "Read text", exact: true }).click();
  await reader.locator(".reader-text").evaluate((el) => {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const node = walker.nextNode()!;
    const range = document.createRange();
    range.setStart(node, 0);
    range.setEnd(node, Math.min(24, node.textContent!.length));
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
    el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
  });
  await reader
    .getByRole("button", { name: "Save note for selected text" })
    .click();
  await reader
    .getByLabel("Your note")
    .fill(noteText);
  await reader.getByRole("button", { name: "Save note", exact: true }).click();
  const note = reader
    .locator(".note-card")
    .filter({ hasText: noteText });
  await expect(note).toBeVisible();
  await note.getByRole("button", { name: "Delete note", exact: true }).click();
  await expect(note).not.toBeVisible();
});
test("exports download and dark mode persists on mobile", async ({ page }) => {
  await samples(page);
  await page.getByRole("button", { name: "Export", exact: true }).click();
  const modal = page.getByRole("dialog", { name: "Export analysis" });
  await modal.getByRole("checkbox").first().check();
  await modal.getByLabel("Download format").selectOption("csv");
  const download = page.waitForEvent("download");
  await modal.getByRole("button", { name: "Generate & download" }).click();
  expect((await download).suggestedFilename()).toBe("filinglens-analysis.csv");
  await page
    .getByRole("button", { name: "Use dark theme", exact: true })
    .click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.setViewportSize({ width: 390, height: 844 });
  for (const label of [
    "Ask a question",
    "My reports",
    "Compare numbers",
    "Dashboard",
    "Knowledge graph",
  ])
    await expect(
      page
        .getByRole("navigation")
        .getByRole("button", { name: label, exact: true }),
    ).toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../docs/screenshots/dark-mobile.png",
    fullPage: true,
  });
});

test("account screen signs in and sends bearer headers", async ({ page }) => {
  const token =
    "test." +
    Buffer.from(
      JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }),
    ).toString("base64url") +
    ".signature";
  await page.route("**/api/auth/config", (route) =>
    route.fulfill({ json: { enabled: true } }),
  );
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({
      json: {
        access_token: token,
        token_type: "bearer",
        user: {
          id: "mock-user",
          full_name: "Test Analyst",
          email: "analyst@example.test",
          role: "analyst",
        },
      },
    }),
  );
  let authorised = false;
  page.on("request", (request) => {
    if (
      request.url().endsWith("/api/documents") &&
      request.headers()["authorization"] === `Bearer ${token}`
    )
      authorised = true;
  });
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("analyst@example.test");
  await page.getByLabel("Password", { exact: true }).fill("test-password-long");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Test Analyst", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Reports to use")).toBeVisible();
  expect(authorised).toBeTruthy();
  await page.getByText("Test Analyst", { exact: true }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back" }),
  ).toBeVisible();
});

test("knowledge graph nodes open their source mentions", async ({ page }) => {
  await page.route("**/knowledge-graph", (route) =>
    route.fulfill({
      json: {
        enabled: true,
        status: "complete",
        error: null,
        limitation: "Edges mean mentioned together in a sentence.",
        nodes: [
          {
            id: "node-1",
            text: "TCS",
            type: "COMPANY",
            page_index: 0,
            count: 1,
            mentions: [
              { page_index: 0, sentence: "TCS synthetic quarterly results." },
            ],
          },
        ],
        edges: [],
      },
    }),
  );
  await samples(page);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Knowledge graph", exact: true })
    .click();
  await page.getByRole("button", { name: "TCS · 1", exact: true }).click();
  await page.getByRole("button", { name: "Open page 1", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Evidence reader" }),
  ).toBeVisible();
});

test("PDF rendering failure offers the standard viewer", async ({ page }) => {
  await page.route("**/pdf.worker*.mjs", (route) => route.abort());
  await samples(page);
  await page
    .getByRole("button", { name: "Compare revenue growth", exact: true })
    .click();
  await page.locator(".citation").first().click();
  const reader = page.getByRole("dialog", { name: "Evidence reader" });
  await reader.getByRole("button", { name: "View PDF", exact: true }).click();
  await expect(reader.locator("iframe")).toBeVisible();
  await expect(reader).toContainText("Showing the standard viewer");
});
