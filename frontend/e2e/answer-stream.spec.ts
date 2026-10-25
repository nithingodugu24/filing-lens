import { test, expect, type Page } from "@playwright/test";
const answer = {
  run_id: "stream-ui-fixture",
  mode: "openai",
  answer_kind: "answer",
  summary: "",
  report_overviews: [],
  suggestions: [],
  claims: [
    {
      text: "The finished source-linked answer.",
      citation_ids: ["fixture-source"],
      supporting_quote: "A fixture source sentence.",
      kind: "management statement",
    },
  ],
  evidence: [
    {
      id: "fixture-source",
      document_id: "fixture-document",
      title: "UI fixture",
      company: "Example Ltd",
      page_index: 0,
      text: "A fixture source sentence.",
      synthetic: true,
    },
  ],
  calculations: [],
  metric_answers: [],
  abstained: false,
  limitation: "From selected source passages.",
  configuration: {},
  usage: {},
  confidence: 0.8,
};
async function setup(
  page: Page,
  behavior: "complete" | "interrupt" = "complete",
) {
  await page.addInitScript(
    ({ answer, behavior }) => {
      const original = window.fetch.bind(window);
      window.fetch = async (input, options) => {
        const path =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.pathname
              : input.url;
        if (!path.endsWith("/questions") && !path.endsWith("/conversations"))
          return original(input, options);
        const encoder = new TextEncoder();
        let timer: ReturnType<typeof setTimeout>;
        return new Response(
          new ReadableStream({
            start(controller) {
              // CRLF and a currency symbol split across byte boundaries exercise framing/UTF-8.
              const prefix = encoder.encode(
                "event: delta\r\ndata: " +
                  JSON.stringify({
                    text: "A streamed explanation in ₹ crore.",
                  }) +
                  "\r\n\r\n",
              );
              for (let i = 0; i < prefix.length; i += 3)
                controller.enqueue(prefix.slice(i, i + 3));
              timer = setTimeout(() => {
                if (behavior === "complete")
                  controller.enqueue(
                    encoder.encode(
                      "event: done\ndata: " + JSON.stringify(answer) + "\n\n",
                    ),
                  );
                controller.close();
              }, 1500);
              options?.signal?.addEventListener(
                "abort",
                () => {
                  clearTimeout(timer);
                  (
                    window as Window & { streamCancelled?: boolean }
                  ).streamCancelled = true;
                  controller.error(new DOMException("Aborted", "AbortError"));
                },
                { once: true },
              );
            },
            cancel() {
              clearTimeout(timer);
            },
          }),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      };
    },
    { answer, behavior },
  );
  await page.goto("/");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Ask a question", exact: true })
    .click();
  await page.getByLabel("Reports to use").selectOption("samples");
  await expect(
    page.getByText("4 sample reports ready", { exact: true }),
  ).toBeVisible();
}

test("answer text appears before completion and is replaced with the checked answer", async ({
  page,
}) => {
  await setup(page);
  await page.getByLabel("Your question").fill("Explain utilisation changes");
  await page.getByRole("button", { name: "Find answer", exact: true }).click();
  await expect(page.locator(".streaming-text")).toContainText(
    "A streamed explanation in ₹ crore.",
  );
  await expect(page.locator(".streaming-text")).toBeInViewport();
  await expect(
    page.getByText("Draft · source checks pending", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".answer-section")).not.toBeVisible();
  await expect(page.locator(".claim")).toContainText(
    "The finished source-linked answer.",
  );
  await expect(page.locator(".streaming-answer")).not.toBeVisible();
  await expect(page.locator(".claim .citation")).toContainText(
    "Open Example Ltd source",
  );
});

test("stop cancels streaming and leaves the question available to edit", async ({
  page,
}) => {
  await setup(page);
  await page.getByLabel("Your question").fill("Explain utilisation changes");
  await page.getByRole("button", { name: "Find answer", exact: true }).click();
  await expect(page.locator(".streaming-text")).toBeVisible();
  await page.getByRole("button", { name: "Stop answer", exact: true }).click();
  await expect(page.locator(".streaming-answer")).not.toBeVisible();
  await expect(page.getByLabel("Your question")).toHaveValue(
    "Explain utilisation changes",
  );
  await expect(
    page.getByRole("button", { name: "Find answer", exact: true }),
  ).toBeEnabled();
  expect(
    await page.evaluate(
      () => (window as Window & { streamCancelled?: boolean }).streamCancelled,
    ),
  ).toBeTruthy();
  await expect(page.locator(".answer-section")).not.toBeVisible();
});

test("an interrupted stream clears its draft and explains the failure", async ({
  page,
}) => {
  await setup(page, "interrupt");
  await page.getByLabel("Your question").fill("Explain utilisation changes");
  await page.getByRole("button", { name: "Find answer", exact: true }).click();
  await expect(page.locator(".streaming-text")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "The connection stopped before the answer finished.",
  );
  await expect(page.locator(".streaming-answer")).not.toBeVisible();
  await expect(page.locator(".answer-section")).not.toBeVisible();
});

test("conversation answers stream before a completed turn is added", async ({
  page,
}) => {
  await setup(page);
  await page
    .getByRole("button", { name: "Conversation mode", exact: true })
    .click();
  await page.getByLabel("Ask a follow-up").fill("Explain utilisation changes");
  await page
    .getByRole("button", { name: "Send question", exact: true })
    .click();
  await expect(page.locator(".conversation .streaming-text")).toContainText(
    "A streamed explanation",
  );
  await expect(page.locator(".chat-turn")).toHaveCount(0);
  await expect(page.locator(".chat-turn")).toHaveCount(1);
  await expect(page.locator(".chat-answer")).toContainText(
    "The finished source-linked answer.",
  );
});
