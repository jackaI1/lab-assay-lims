import { createServer } from "node:http";
import { createHash, randomBytes, randomUUID } from "node:crypto";
import { MAX_BYTES, numeric, requestIdValid } from "../extension/protocol.js";
type Receipt = {
  receipt: string;
  count: number;
  digest: string;
  expires: number;
};
export function createReceiver({
  now = Date.now,
}: { now?: () => number } = {}) {
  const tokens = new Map<string, number>();
  const receipts = new Map<string, Receipt>();
  const server = createServer(async (req, res) => {
    res.setHeader("Content-Type", "application/json");
    res.setHeader("Cache-Control", "no-store");
    const reply = (status: number, value: unknown) => {
      res.writeHead(status);
      res.end(JSON.stringify(value));
    };
    const origin = req.headers.origin;
    if (origin && !/^chrome-extension:\/\/[a-p]{32}$/.test(origin))
      return reply(403, { error: "Extension requests only" });
    if (req.method === "GET" && req.url === "/health")
      return reply(200, { status: "ready", receipts: receipts.size });
    if (req.method !== "POST" || !["/token", "/send"].includes(req.url ?? ""))
      return reply(404, { error: "Not found" });
    if (!req.headers["content-type"]?.startsWith("application/json"))
      return reply(415, { error: "JSON required" });
    for (const [k, v] of tokens) if (v <= now()) tokens.delete(k);
    for (const [k, v] of receipts) if (v.expires <= now()) receipts.delete(k);
    let size = 0;
    const chunks: Buffer[] = [];
    try {
      for await (const chunk of req) {
        size += chunk.length;
        if (size > MAX_BYTES * 15) {
          reply(413, { error: "Batch too large" });
          return;
        }
        chunks.push(chunk);
      }
      const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      if (req.url === "/token") {
        if (tokens.size >= 1000)
          return reply(429, { error: "Too many tokens" });
        const token = randomBytes(32).toString("hex");
        tokens.set(token, now() + 30000);
        return reply(200, { token, expiresIn: 30 });
      }
      const token = (req.headers.authorization ?? "").replace(/^Bearer /, "");
      const expiry = tokens.get(token);
      tokens.delete(token);
      if (!expiry || expiry <= now())
        return reply(401, { error: "Expired or invalid token" });
      if (
        !body ||
        !requestIdValid(body.requestId) ||
        !numeric(body.patientId) ||
        !Array.isArray(body.documents) ||
        body.documents.length < 1 ||
        body.documents.length > 10
      )
        return reply(400, { error: "Invalid batch" });
      const ids = new Set();
      for (const d of body.documents) {
        if (
          !d ||
          !numeric(d.id) ||
          ids.has(d.id) ||
          typeof d.name !== "string" ||
          !d.name.trim() ||
          d.name.length > 200 ||
          typeof d.mime !== "string" ||
          ![
            "application/pdf",
            "text/plain",
            "image/png",
            "image/jpeg",
          ].includes(d.mime) ||
          typeof d.base64 !== "string" ||
          !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(
            d.base64,
          ) ||
          !d.base64.length ||
          Buffer.byteLength(d.base64, "base64") > MAX_BYTES
        )
          return reply(400, { error: "Invalid document" });
        ids.add(d.id);
      }
      const digest = createHash("sha256")
        .update(JSON.stringify(body))
        .digest("hex");
      const existing = receipts.get(body.requestId);
      if (existing && existing.digest !== digest)
        return reply(409, { error: "Selection changed; start a new send" });
      if (!existing && receipts.size >= 1000)
        return reply(429, { error: "Receiver busy" });
      const receipt = existing ?? {
        receipt: randomUUID(),
        count: body.documents.length,
        digest,
        expires: now() + 600000,
      };
      receipts.set(body.requestId, receipt);
      // Document bytes are consumed here, then discarded. Only a bounded receipt remains.
      reply(200, { receipt: receipt.receipt, count: receipt.count });
    } catch {
      if (!res.headersSent) reply(400, { error: "Invalid JSON" });
    }
  });
  server.requestTimeout = 15000;
  server.headersTimeout = 10000;
  return { server, receipts };
}
