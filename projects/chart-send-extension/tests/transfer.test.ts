import { test } from "node:test";
import assert from "node:assert/strict";
import { sendDocuments } from "../extension/transfer.js";
const message = {
  type: "SEND" as const,
  patientId: "1",
  requestId: "00000000-0000-4000-8000-000000000001",
  documents: [{ id: "2", name: "fictional.txt" }],
};
const sender =
  "http://127.0.0.1:8080/openemr/controller.php?document&patient_id=1";
test("transfers bytes with credentials only to OpenEMR and a fresh token only to receiver", async () => {
  const calls: { url: string; init: RequestInit }[] = [];
  const fetcher = async (
    input: string | URL | Request,
    init: RequestInit = {},
  ) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.includes("8080"))
      return new Response("FICTIONAL ONLY", {
        headers: { "Content-Type": "text/plain" },
      });
    if (url.endsWith("/token")) return Response.json({ token: "x".repeat(64) });
    const body = JSON.parse(init.body as string);
    assert.equal(body.documents[0].base64, "RklDVElPTkFMIE9OTFk=");
    return Response.json({ count: 1, receipt: "receipt-1" });
  };
  assert.deepEqual(
    await sendDocuments(message, sender, "http://127.0.0.1:4318", fetcher),
    { ok: true, count: 1, receipt: "receipt-1" },
  );
  assert.equal(calls[0].init.credentials, "include");
  assert.equal(calls[1].init.credentials, "omit");
  assert.equal(
    (calls[2].init.headers as Record<string, string>).Authorization,
    `Bearer ${"x".repeat(64)}`,
  );
  assert.equal(
    calls.every((c) => c.init.redirect === "error"),
    true,
  );
});
test("blocks forged messages before network and reports offline, expired-token and download failures", async () => {
  let calls = 0;
  const offline = async () => {
    calls++;
    throw new TypeError("network");
  };
  assert.equal(
    (
      await sendDocuments(
        message,
        "https://evil.test",
        "http://127.0.0.1:4318",
        offline,
      )
    ).ok,
    false,
  );
  assert.equal(calls, 0);
  assert.deepEqual(
    await sendDocuments(message, sender, "http://127.0.0.1:4318", offline),
    {
      ok: false,
      retryable: true,
      error:
        "Connection failed or timed out. Check OpenEMR and the receiver, then retry.",
    },
  );
  for (const response of [
    new Response("login", { headers: { "Content-Type": "text/html" } }),
    new Response("no", { status: 403 }),
    new Response("x".repeat(1024 * 1024 + 1), {
      headers: { "Content-Type": "text/plain" },
    }),
  ]) {
    const result = await sendDocuments(
      message,
      sender,
      "http://127.0.0.1:4318",
      async () => response,
    );
    assert.equal(result.ok, false);
    if (!result.ok) assert.equal(result.retryable, false);
  }
  const result = await sendDocuments(
    message,
    sender,
    "http://127.0.0.1:4318",
    async (input) =>
      String(input).includes("8080")
        ? new Response("x", { headers: { "Content-Type": "text/plain" } })
        : String(input).endsWith("/token")
          ? Response.json({ token: "x".repeat(64) })
          : new Response("", { status: 401 }),
  );
  assert.equal(result.ok, false);
  if (!result.ok) assert.equal(result.retryable, true);
});
