import { test } from "node:test";
import assert from "node:assert/strict";
import { createReceiver } from "../receiver/server.js";
const batch = {
  requestId: "00000000-0000-4000-8000-000000000001",
  patientId: "1",
  documents: [
    {
      id: "2",
      name: "fictional.txt",
      mime: "text/plain",
      base64: Buffer.from("FICTIONAL ONLY").toString("base64"),
    },
  ],
};
test("requires a token, expires it, rejects replay, and deduplicates a safe retry", async () => {
  let now = 1000;
  const app = createReceiver({ now: () => now });
  await new Promise<void>((resolve) =>
    app.server.listen(0, "127.0.0.1", resolve),
  );
  const addr = app.server.address() as { port: number };
  const base = `http://127.0.0.1:${addr.port}`;
  const post = (path: string, data: unknown, token = "") =>
    fetch(base + path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    });
  const token = async () =>
    (await (await post("/token", {})).json()).token as string;
  try {
    assert.equal((await post("/send", batch)).status, 401);
    let t = await token();
    now += 30001;
    assert.equal((await post("/send", batch, t)).status, 401);
    t = await token();
    const response = await post("/send", batch, t);
    assert.equal(response.status, 200);
    const receipt = await response.json();
    assert.equal(receipt.count, 1);
    assert.equal((await post("/send", batch, t)).status, 401);
    const retry = await post("/send", batch, await token());
    assert.deepEqual(await retry.json(), receipt);
    assert.equal(app.receipts.size, 1);
    assert.equal(
      JSON.stringify([...app.receipts.values()]).includes("FICTIONAL"),
      false,
    );
    assert.equal(
      (await post("/send", { ...batch, documents: [] }, await token())).status,
      400,
    );
    assert.equal(
      (await post("/send", { ...batch, requestId: "bad" }, await token()))
        .status,
      400,
    );
    assert.equal(
      (
        await post(
          "/send",
          {
            ...batch,
            requestId: "00000000-0000-4000-8000-000000000002",
            documents: [{ ...batch.documents[0], base64: "!bad" }],
          },
          await token(),
        )
      ).status,
      400,
    );
    assert.equal(
      (
        await post(
          "/send",
          {
            ...batch,
            documents: [
              {
                ...batch.documents[0],
                base64: Buffer.from("changed").toString("base64"),
              },
            ],
          },
          await token(),
        )
      ).status,
      409,
    );
    const evil = await fetch(base + "/token", {
      method: "POST",
      headers: {
        Origin: "http://evil.test",
        "Content-Type": "application/json",
      },
      body: "{}",
    });
    assert.equal(evil.status, 403);
  } finally {
    await new Promise<void>((resolve, reject) =>
      app.server.close((e) => (e ? reject(e) : resolve())),
    );
  }
});
test("rejects empty, oversized, unsupported and duplicate document payloads without receipts", async () => {
  const app = createReceiver();
  await new Promise<void>((r) => app.server.listen(0, "127.0.0.1", r));
  const base = `http://127.0.0.1:${(app.server.address() as { port: number }).port}`;
  const post = (path: string, data: unknown, token = "") =>
    fetch(base + path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    });
  try {
    for (const documents of [
      [{ ...batch.documents[0], base64: "" }],
      [
        {
          ...batch.documents[0],
          base64: Buffer.alloc(1024 * 1024 + 1).toString("base64"),
        },
      ],
      [{ ...batch.documents[0], mime: "text/html" }],
      [batch.documents[0], batch.documents[0]],
    ]) {
      const { token } = await (await post("/token", {})).json();
      assert.equal(
        (await post("/send", { ...batch, documents }, token)).status,
        400,
      );
    }
    assert.equal(app.receipts.size, 0);
  } finally {
    await new Promise<void>((r) => app.server.close(() => r()));
  }
});
