import {
  test,
  expect,
  chromium,
  type BrowserContext,
  type Page,
  type Worker,
} from "@playwright/test";
import { createServer, type Server } from "node:http";
import { mkdtemp, rm, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { createReceiver } from "../receiver/server.js";
const real = process.env.OPENEMR === "1";
const chart =
  "http://127.0.0.1:8080/openemr/controller.php?document&list&patient_id=1";
let context: BrowserContext,
  worker: Worker,
  page: Page,
  options: Page,
  profile: string;
let receiver: ReturnType<typeof createReceiver>,
  fixture: Server | undefined,
  proxy: Server | undefined;
let mode: "normal" | "bad" | "expired" = "normal";
const listen = (server: Server, port: number) =>
  new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", resolve);
  });
const close = (server: Server) =>
  new Promise<void>((resolve, reject) =>
    server.close((e) => (e ? reject(e) : resolve())),
  );
const panel = () => page.locator("#chart-send-extension");
async function openChart() {
  await page.goto(chart);
  await expect(panel()).toBeVisible();
}
async function pick() {
  await panel().getByRole("checkbox").first().check();
}
test.beforeAll(async () => {
  profile = await mkdtemp(join(tmpdir(), "chart-send-browser-"));
  try {
    receiver = createReceiver();
    await listen(receiver.server, 4318);
    if (!real) {
      fixture = createServer((req, res) => {
        const u = new URL(req.url!, "http://127.0.0.1:8080");
        if (u.searchParams.has("retrieve")) {
          if (mode === "bad") {
            res.writeHead(403);
            res.end("Not allowed");
            return;
          }
          res.setHeader(
            "Content-Type",
            mode === "expired" ? "text/html" : "text/plain",
          );
          res.end(
            mode === "expired"
              ? "<html>Sign in</html>"
              : "FICTIONAL ONLY: River lab example. No real patient information.\n",
          );
          return;
        }
        res.setHeader("Content-Type", "text/html");
        res.end(
          `<!doctype html><title>OpenEMR document markup fixture</title><h1>Fictional River</h1><a href="/openemr/controller.php?document&view&patient_id=1&doc_id=1&">fictional-lab.txt</a><a href="/openemr/controller.php?document&view&patient_id=1&doc_id=2&">fictional-referral.txt</a><a href="/openemr/controller.php?document&view&patient_id=2&doc_id=3&">Other patient's file</a>`,
        );
      });
      await listen(fixture, 8080);
    }
    const extension = resolve("dist");
    context = await chromium.launchPersistentContext(profile, {
      channel: "chromium",
      headless: true,
      args: [
        `--disable-extensions-except=${extension}`,
        `--load-extension=${extension}`,
      ],
    });
    worker =
      context.serviceWorkers()[0] ??
      (await context.waitForEvent("serviceworker"));
    // Record only this test's owned resources. Context.close owns all its tabs/processes.
    await mkdir("test-results", { recursive: true });
    await writeFile(
      "test-results/resources.json",
      JSON.stringify(
        {
          owner: "chart-send Playwright",
          started: new Date().toISOString(),
          testPid: process.pid,
          ports: real ? [4318] : [4318, 8080],
          cleanup:
            "Playwright afterAll: context.close(), server.close(), rm(profile)",
          processes: execFileSync("ps", ["-axo", "pid,ppid,lstart,command"], {
            encoding: "utf8",
            maxBuffer: 4 * 1024 * 1024,
          })
            .split("\n")
            .filter((line) => line.includes(profile)),
        },
        null,
        2,
      ),
    );
    page = context.pages()[0] ?? (await context.newPage());
    options = await context.newPage();
    if (real) {
      await page.goto(
        "http://127.0.0.1:8080/openemr/interface/login/login.php?site=default",
      );
      await page.locator("#authUser").fill("admin");
      await page.locator("#clearPass").fill("fictional-demo-only");
      await page.locator("button[type=submit]").click();
      await page.waitForURL("**/interface/main/**");
      await page.goto(
        "http://127.0.0.1:8080/openemr/interface/patient_file/summary/demographics.php?set_pid=1",
      );
    }
    await options.goto(
      `chrome-extension://${worker.url().split("/")[2]}/options.html`,
    );
  } catch (error) {
    await cleanup();
    throw error;
  }
});
async function cleanup() {
  if (context) await context.close();
  if (fixture?.listening) await close(fixture);
  if (proxy?.listening) await close(proxy);
  if (receiver?.server.listening) await close(receiver.server);
  if (profile) await rm(profile, { recursive: true, force: true });
}
test.afterAll(cleanup);
test("loaded extension sends only selected native documents and stores only settings", async () => {
  await openChart();
  await expect(panel().getByRole("checkbox")).toHaveCount(2);
  await panel()
    .getByRole("button", { name: "Send selected", exact: true })
    .click();
  await expect(panel().getByRole("status")).toContainText("Choose between");
  await pick();
  await panel()
    .getByRole("button", { name: "Send selected", exact: true })
    .click();
  await expect(panel().getByRole("status")).toContainText("Sent 1 document.", {
    timeout: 25000,
  });
  expect(receiver.receipts.size).toBe(1);
  // Compare the receiver's digest with a hand-specified fictional file.
  const [requestId, receipt] = [...receiver.receipts.entries()][0];
  const name = await panel()
    .getByRole("checkbox")
    .first()
    .getAttribute("data-name");
  expect(receipt.digest).toBe(
    createHash("sha256")
      .update(
        JSON.stringify({
          requestId,
          patientId: "1",
          documents: [
            {
              id: "1",
              name,
              mime: "text/plain",
              base64: Buffer.from(
                "FICTIONAL ONLY: River lab example. No real patient information.\n",
              ).toString("base64"),
            },
          ],
        }),
      )
      .digest("hex"),
  );
  await options.getByLabel("Receiver address").fill("http://127.0.0.1:4318");
  await options.getByRole("button", { name: "Save address" }).click();
  await expect(options.getByRole("status")).toHaveText("Address saved.");
  expect(await worker.evaluate(() => chrome.storage.local.get(null))).toEqual({
    receiver: "http://127.0.0.1:4318",
  });
  expect(await worker.evaluate(() => chrome.storage.sync.get(null))).toEqual(
    {},
  );
  expect(await worker.evaluate(() => chrome.storage.session.get(null))).toEqual(
    {},
  );
  await page.screenshot({ path: "test-results/chart-send.png" });
});
test("options reject remote receivers and offline send recovers through Retry", async () => {
  await options.getByLabel("Receiver address").fill("https://example.com");
  await options.getByRole("button", { name: "Save address" }).click();
  await expect(options.getByRole("status")).toContainText(
    "Use http://127.0.0.1",
  );
  await options.getByLabel("Receiver address").fill("http://127.0.0.1:4319");
  await options.getByRole("button", { name: "Save address" }).click();
  await expect(options.getByRole("status")).toHaveText("Address saved.");
  await openChart();
  await pick();
  await panel()
    .getByRole("button", { name: "Send selected", exact: true })
    .click();
  await expect(
    panel().getByRole("button", { name: "Retry send", exact: true }),
  ).toBeEnabled({ timeout: 25000 });
  await options.getByLabel("Receiver address").fill("http://127.0.0.1:4318");
  await options.getByRole("button", { name: "Save address" }).click();
  await expect(options.getByRole("status")).toHaveText("Address saved.");
  await panel()
    .getByRole("button", { name: "Retry send", exact: true })
    .click();
  await expect(panel().getByRole("status")).toContainText("Sent 1 document.", {
    timeout: 25000,
  });
});
test("a lost acknowledgement can be retried without accepting the batch twice", async () => {
  let lost = false;
  proxy = createServer(async (req, res) => {
    const chunks: Buffer[] = [];
    for await (const c of req) chunks.push(c);
    const response = await fetch(`http://127.0.0.1:4318${req.url}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: req.headers.authorization ?? "",
      },
      body: Buffer.concat(chunks),
    });
    const text = await response.text();
    if (req.url === "/send" && !lost) {
      lost = true;
      res.writeHead(503);
      res.end("{}");
      return;
    }
    res.writeHead(response.status, { "Content-Type": "application/json" });
    res.end(text);
  });
  await listen(proxy, 4319);
  try {
    await options.getByLabel("Receiver address").fill("http://127.0.0.1:4319");
    await options.getByRole("button", { name: "Save address" }).click();
    await expect(options.getByRole("status")).toHaveText("Address saved.");
    await openChart();
    await pick();
    const before = receiver.receipts.size;
    await panel()
      .getByRole("button", { name: "Send selected", exact: true })
      .click();
    await expect(
      panel().getByRole("button", { name: "Retry send", exact: true }),
    ).toBeEnabled();
    expect(receiver.receipts.size).toBe(before + 1);
    await panel()
      .getByRole("button", { name: "Retry send", exact: true })
      .click();
    await expect(panel().getByRole("status")).toContainText("Sent 1 document.");
    expect(receiver.receipts.size).toBe(before + 1);
  } finally {
    await close(proxy);
    await options.getByLabel("Receiver address").fill("http://127.0.0.1:4318");
    await options.getByRole("button", { name: "Save address" }).click();
    await expect(options.getByRole("status")).toHaveText("Address saved.");
  }
});
test("permission and message boundaries reject untrusted contexts", async () => {
  expect(
    await worker.evaluate(() =>
      chrome.permissions.contains({ origins: ["https://example.com/*"] }),
    ),
  ).toBe(false);
  expect(
    await worker.evaluate(() =>
      chrome.permissions.contains({ origins: ["http://localhost/*"] }),
    ),
  ).toBe(false);
  const permissions = await worker.evaluate(() => chrome.permissions.getAll());
  expect(permissions.permissions).toEqual(["storage"]);
  expect(
    permissions.origins?.every((origin) =>
      origin.startsWith("http://127.0.0.1/"),
    ),
  ).toBe(true);
  const result = await options.evaluate(() =>
    chrome.runtime.sendMessage({
      type: "SEND",
      patientId: "1",
      requestId: crypto.randomUUID(),
      documents: [{ id: "1", name: "x" }],
    }),
  );
  expect(result.ok).toBe(false);
  await page.goto("http://127.0.0.1:8080/openemr/interface/login/login.php");
  await expect(panel()).toHaveCount(0);
  await page.goto(
    "http://localhost:8080/openemr/controller.php?document&patient_id=1",
  );
  await expect(panel()).toHaveCount(0);
});
test("document access and expired sessions show a non-retryable failure", async () => {
  if (real) {
    // A real expired OpenEMR session must never be forwarded as a document.
    await openChart();
    await pick();
    await context.clearCookies();
    await panel()
      .getByRole("button", { name: "Send selected", exact: true })
      .click();
    await expect(panel().getByRole("status")).toContainText(
      "expired OpenEMR session",
    );
    await expect(
      panel().getByRole("button", { name: "Change selection to try again" }),
    ).toBeDisabled();
  } else {
    for (const failure of ["bad", "expired"] as const) {
      mode = failure;
      await openChart();
      await pick();
      await panel()
        .getByRole("button", { name: "Send selected", exact: true })
        .click();
      await expect(
        panel().getByRole("button", { name: "Change selection to try again" }),
      ).toBeDisabled();
      await expect(panel().getByRole("status")).toContainText(
        failure === "bad" ? "OpenEMR refused" : "expired OpenEMR session",
      );
    }
    mode = "normal";
  }
});
