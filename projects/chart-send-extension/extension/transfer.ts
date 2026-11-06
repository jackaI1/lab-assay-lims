import {
  MAX_BYTES,
  documentUrl,
  receiverAddress,
  validateSend,
  type Result,
} from "./protocol.js";
class TransferError extends Error {
  constructor(
    message: string,
    readonly retryable = false,
  ) {
    super(message);
  }
}
async function boundedBody(
  response: Response,
  limit: number,
): Promise<Uint8Array> {
  if (Number(response.headers.get("Content-Length")) > limit)
    throw new TransferError("A document exceeds the 1 MiB limit.");
  const reader = response.body?.getReader();
  if (!reader) throw new TransferError("The document is empty.");
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > limit)
        throw new TransferError("A document exceeds the 1 MiB limit.");
      chunks.push(value);
    }
  } finally {
    await reader.cancel();
  }
  if (size === 0) throw new TransferError("The document is empty.");
  const body = new Uint8Array(size);
  let offset = 0;
  for (const c of chunks) {
    body.set(c, offset);
    offset += c.length;
  }
  return body;
}
export async function sendDocuments(
  value: unknown,
  senderUrl: string,
  receiver: unknown,
  fetcher: typeof fetch = fetch,
): Promise<Result> {
  try {
    const m = validateSend(value, senderUrl);
    const base = receiverAddress(receiver);
    const signal = AbortSignal.timeout(20000);
    const documents = [];
    for (const d of m.documents) {
      const response = await fetcher(documentUrl(m.patientId, d.id), {
        credentials: "include",
        redirect: "error",
        cache: "no-store",
        signal,
      });
      if (!response.ok)
        throw new TransferError(
          "OpenEMR refused a document. Sign in again and check access.",
        );
      const mime = (response.headers.get("Content-Type") ?? "")
        .split(";")[0]
        .trim()
        .toLowerCase();
      if (
        !["application/pdf", "text/plain", "image/png", "image/jpeg"].includes(
          mime,
        )
      )
        throw new TransferError(
          "Unsupported document or expired OpenEMR session. Sign in and select PDF, text, PNG or JPEG files.",
        );
      const bytes = await boundedBody(response, MAX_BYTES);
      let binary = "";
      for (let offset = 0; offset < bytes.length; offset += 8192)
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
      documents.push({ ...d, mime, base64: btoa(binary) });
    }
    const post = (path: string, body: unknown, token?: string) =>
      fetcher(base + path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        credentials: "omit",
        redirect: "error",
        cache: "no-store",
        signal,
      });
    const auth = await post("/token", {});
    if (!auth.ok)
      throw new TransferError(
        "Receiver could not issue a token. Check it and retry.",
        true,
      );
    const { token } = await auth.json();
    if (typeof token !== "string" || token.length !== 64)
      throw new TransferError("Receiver returned an invalid token.");
    const result = await post(
      "/send",
      { requestId: m.requestId, patientId: m.patientId, documents },
      token,
    );
    if (!result.ok)
      throw new TransferError(
        result.status === 409
          ? "Documents changed after the previous attempt. Change the selection to start a new send."
          : `Receiver rejected the send (${result.status}). Check it and retry.`,
        result.status === 401 || result.status === 429 || result.status >= 500,
      );
    const receipt = await result.json();
    if (
      receipt.count !== documents.length ||
      typeof receipt.receipt !== "string"
    )
      throw new TransferError("Receiver returned an invalid receipt.");
    return { ok: true, count: receipt.count, receipt: receipt.receipt };
  } catch (error) {
    if (
      error instanceof TypeError ||
      (error instanceof DOMException &&
        ["AbortError", "TimeoutError"].includes(error.name))
    )
      return {
        ok: false,
        retryable: true,
        error:
          "Connection failed or timed out. Check OpenEMR and the receiver, then retry.",
      };
    return {
      ok: false,
      retryable: error instanceof TransferError && error.retryable,
      error: error instanceof Error ? error.message : "Send failed.",
    };
  }
}
