import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("adds, persists, prioritizes, calls and completes a practice arrival", async ({
  page,
  context,
}) => {
  await page
    .getByLabel("Practice visit type")
    .selectOption("Practice screening");
  await page.getByRole("button", { name: "Add practice arrival" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "D-004 added" }),
  ).toBeVisible();
  await expect(page.getByText("4 waiting", { exact: true })).toBeVisible();
  const cookie = (await context.cookies()).find(
    (c) => c.name === "clinic-demo-session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Lax");
  await page.reload();
  await expect(page.getByText("4 waiting", { exact: true })).toBeVisible();
  const ticket = page
    .getByRole("listitem")
    .filter({ has: page.getByRole("heading", { name: "D-004", exact: true }) });
  await ticket.getByRole("combobox").selectOption("Soon");
  await ticket.getByRole("button", { name: "Save priority for D-004" }).click();
  await expect(ticket.getByRole("status")).toHaveText(
    "Priority saved. Waiting order updated.",
  );
  await expect(
    page
      .getByRole("list", { name: "Waiting tickets" })
      .getByRole("listitem")
      .first(),
  ).toContainText("D-002");
  await page.getByRole("button", { name: "Call next ticket" }).click();
  await expect(
    page.getByRole("button", { name: "Complete D-002" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Complete D-002" }).click();
  await page.getByText("Completed tickets (1)", { exact: true }).click();
  await expect(page.locator(".completed-list")).toContainText("D-002");
});

test("shows accessible server validation and keyboard navigation", async ({
  page,
}) => {
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to intake queue" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Add practice arrival" }).click();
  await expect(page.getByLabel("Practice visit type")).toBeFocused();
  await expect(page.getByLabel("Practice visit type")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await expect(
    page.getByText("Choose one of the practice visit types."),
  ).toBeVisible();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
});

test("filters the view while calling next from the full queue", async ({
  page,
}) => {
  await page.getByRole("link", { name: "Flexible", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "Waiting tickets" }).getByRole("listitem"),
  ).toHaveCount(1);
  await expect(
    page.getByRole("heading", { name: "D-003", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Call next ticket" }).click();
  await expect(
    page.getByRole("button", { name: "Complete D-002" }),
  ).toBeVisible();
});

test("has no automated accessibility violations or horizontal overflow", async ({
  page,
}, testInfo) => {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("queue.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Call next ticket" }).click();
  await expect(
    page.getByRole("button", { name: "Complete D-002" }),
  ).toBeVisible();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
});

test("keeps browser queues separate and resets only the current queue", async ({
  page,
  browser,
}) => {
  await page
    .getByLabel("Practice visit type")
    .selectOption("Practice check-in");
  await page.getByRole("button", { name: "Add practice arrival" }).click();
  await expect(page.getByText("4 waiting", { exact: true })).toBeVisible();
  const other = await browser.newContext();
  try {
    const otherPage = await other.newPage();
    await otherPage.goto("/");
    await expect(
      otherPage.getByText("3 waiting", { exact: true }),
    ).toBeVisible();
    await page.getByText("Start the demo again", { exact: true }).click();
    await page.getByLabel("Clear my practice queue").check();
    await page.getByRole("button", { name: "Reset demo" }).click();
    await expect(page.getByText("3 waiting", { exact: true })).toBeVisible();
    await expect(
      otherPage.getByText("3 waiting", { exact: true }),
    ).toBeVisible();
  } finally {
    await other.close();
  }
});

test("serves useful edge metadata without any session or ticket data", async ({
  request,
}) => {
  const options = await request.get("/api/intake-options");
  expect(options.status()).toBe(200);
  expect(options.headers()["cache-control"]).toContain("max-age=300");
  expect(await options.json()).toMatchObject({
    demoOnly: true,
    personalDataAllowed: false,
    visits: expect.arrayContaining(["Practice check-in"]),
    priorities: ["Soon", "Standard", "Flexible"],
  });
  const health = await request.get("/api/health");
  expect(await health.json()).toMatchObject({
    status: "ok",
    runtime: "edge",
    check: "liveness",
  });
});

test("submits a practice arrival with JavaScript disabled", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  try {
    const page = await context.newPage();
    await page.goto("/");
    await page
      .getByLabel("Practice visit type")
      .selectOption("Practice follow-up");
    await page.getByRole("button", { name: "Add practice arrival" }).click();
    await expect(page.getByText("4 waiting", { exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByText("4 waiting", { exact: true })).toBeVisible();
  } finally {
    await context.close();
  }
});

test('issues a fresh submission ID for each new arrival', async ({ page }) => {
  const firstId = await page.locator('input[name="requestId"]').inputValue();
  await page.getByLabel('Practice visit type').selectOption('Practice check-in');
  await page.getByRole('button', { name: 'Add practice arrival' }).click();
  await expect(page.getByText('4 waiting', { exact: true })).toBeVisible();
  await expect(page.locator('input[name="requestId"]')).not.toHaveValue(firstId);
  await page.getByLabel('Practice visit type').selectOption('Practice screening');
  await page.getByRole('button', { name: 'Add practice arrival' }).click();
  await expect(page.getByText('5 waiting', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'D-005', exact: true })).toBeVisible();
});
