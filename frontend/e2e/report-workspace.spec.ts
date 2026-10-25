import { test, expect } from "@playwright/test";
const doc = {
  id: "ui-report",
  title: "Example Ltd annual report — UI fixture",
  company: "Example Ltd",
  document_type: "annual_report",
  period_start: "2024-04-01",
  period_end: "2025-03-31",
  publication_date: null,
  source_url: null,
  currency: "INR",
  units: "crore",
  basis: "consolidated",
  synthetic: false,
  status: "indexed",
  warning: null,
  page_count: 2,
  job: null,
};
const evidence = {
  id: "ui-report:p0:t0",
  document_id: doc.id,
  title: doc.title,
  company: doc.company,
  page_index: 0,
  text: "Total income | 110 | 100",
  synthetic: false,
};
const metric = {
  fact_id: "ui-fact",
  document_id: doc.id,
  company: doc.company,
  metric: "total_income",
  label: "Total income",
  value: "110",
  currency: "INR",
  units: "crore",
  basis: "consolidated",
  period_start: doc.period_start,
  period_end: doc.period_end,
  source_page: 1,
  citation_id: evidence.id,
  previous_value: "100",
  previous_period_end: "2024-03-31",
  change_percent: "10",
  verification_method: "automatic",
  source_details: { row_text: evidence.text },
};
const answer = {
  run_id: "ui-run",
  mode: "financial",
  answer_kind: "answer",
  summary: "",
  report_overviews: [],
  suggestions: [],
  claims: [],
  evidence: [evidence],
  calculations: [],
  metric_answers: [metric],
  abstained: false,
  limitation: "Using the latest period in this report.",
  configuration: {},
  usage: {},
  confidence: null,
};
const workspace = {
  financials: [metric],
  evidence: [evidence],
  brief: {
    status: "metrics_only",
    content: { claims: [], evidence: [] },
    error: null,
  },
  coverage: { metric_count: 1, period_count: 2 },
  checks_explained: "Automatic checks are not an independent audit.",
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/documents", (r) => r.fulfill({ json: [doc] }));
  await page.route("**/api/library", (r) => r.fulfill({ json: [] }));
  await page.route("**/api/documents/ui-report/workspace?*", (r) =>
    r.fulfill({ json: workspace }),
  );
  await page.route("**/api/documents/ui-report/pages/*", (r) =>
    r.fulfill({
      json: {
        page_index: 0,
        printed_label: "1",
        text: evidence.text,
        tables: [],
      },
    }),
  );
  await page.route("**/api/history*", (r) => r.fulfill({ json: [] }));
});

test("report overview shows source-linked numbers and accounting basis", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Read less. Understand more." }),
  ).toBeVisible();
  await expect(page.locator(".metric-card")).toContainText("₹110 crore");
  await expect(page.locator(".metric-card")).toContainText("+10% year on year");
  await expect(page.getByLabel("Accounting basis")).toHaveValue("consolidated");
  await page
    .locator(".metric-card")
    .getByRole("button", { name: "PDF page 1", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog", { name: "Evidence reader" })
      .locator(".reader-text"),
  ).toContainText("Total income");
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await expect(
    page
      .getByRole("navigation")
      .getByRole("button", { name: "Report overview", exact: true }),
  ).toBeInViewport();
});

test("overview question stays scoped to the selected report and shows a figure card", async ({
  page,
}) => {
  let filters: Record<string, unknown> = {};
  await page.route("**/api/questions", (r) => {
    filters = r.request().postDataJSON().filters;
    return r.fulfill({ json: answer });
  });
  await page.goto("/");
  await page
    .getByRole("button", {
      name: "What is the total income in crores this year?",
      exact: true,
    })
    .click();
  await expect(page.getByLabel("Question scope")).toHaveValue(doc.id);
  await page.getByRole("button", { name: "Find answer", exact: true }).click();
  await expect(page.locator(".answer-section .metric-card")).toContainText(
    "₹110 crore",
  );
  expect(filters.document_ids).toEqual([doc.id]);
});

test("people directory limits results and opens a source mention", async ({
  page,
}) => {
  await page.route("**/api/documents/ui-report/entities?*", (r) =>
    r.fulfill({
      json: Array.from({ length: 40 }, (_, i) => ({
        id: `entity-${i}`,
        text: `Research Name ${i}`,
        type: "PERSON",
        page_index: 0,
        count: 1,
        mentions: [
          {
            page_index: 0,
            sentence: `Research Name ${i} is mentioned in this UI fixture.`,
          },
        ],
      })),
    }),
  );
  await page.goto("/");
  await page
    .getByText("People and organisations mentioned", { exact: true })
    .click();
  await expect(page.locator(".people-grid>button")).toHaveCount(24);
  await page.getByLabel("Search names").fill("Research Name 29");
  await expect(page.locator(".people-grid>button")).toHaveCount(1);
  await page.locator(".people-grid>button").click();
  await expect(
    page.getByRole("dialog", { name: "Evidence reader" }),
  ).toBeVisible();
});
