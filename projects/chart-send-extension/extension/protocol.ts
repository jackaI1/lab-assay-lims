export const CHART_ORIGIN = "http://127.0.0.1:8080";
export const MAX_BYTES = 1024 * 1024;
export const DEFAULT_RECEIVER = "http://127.0.0.1:4318";
export type Selection = { id: string; name: string };
export type Send = {
  type: "SEND";
  patientId: string;
  requestId: string;
  documents: Selection[];
};
export type Result =
  | { ok: true; count: number; receipt: string }
  | { ok: false; retryable: boolean; error: string };
export const numeric = (v: unknown): v is string =>
  typeof v === "string" && /^[1-9]\d{0,9}$/.test(v);
export const requestIdValid = (v: unknown): v is string =>
  typeof v === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    v,
  );
export function receiverAddress(value: unknown): string {
  if (typeof value !== "string")
    throw new Error("Set a local receiver address in extension options.");
  const u = new URL(value);
  if (
    u.protocol !== "http:" ||
    u.hostname !== "127.0.0.1" ||
    !["4318", "4319"].includes(u.port) ||
    u.username ||
    u.password ||
    u.pathname !== "/" ||
    u.search ||
    u.hash
  )
    throw new Error("Use http://127.0.0.1:4318 or http://127.0.0.1:4319.");
  return u.origin;
}
export function validateSend(value: unknown, senderUrl: string): Send {
  const m = value as Send;
  const u = new URL(senderUrl);
  if (
    u.origin !== CHART_ORIGIN ||
    u.pathname !== "/openemr/controller.php" ||
    !u.searchParams.has("document") ||
    u.searchParams.get("patient_id") !== m?.patientId
  )
    throw new Error("Open the patient document screen before sending.");
  if (
    m?.type !== "SEND" ||
    !numeric(m.patientId) ||
    !requestIdValid(m.requestId) ||
    !Array.isArray(m.documents) ||
    m.documents.length < 1 ||
    m.documents.length > 10 ||
    m.documents.some(
      (d) =>
        !d ||
        !numeric(d.id) ||
        typeof d.name !== "string" ||
        !d.name.trim() ||
        d.name.length > 200,
    ) ||
    new Set(m.documents.map((d) => d.id)).size !== m.documents.length
  )
    throw new Error("Select between 1 and 10 valid documents.");
  return {
    type: "SEND",
    patientId: m.patientId,
    requestId: m.requestId,
    documents: m.documents.map(({ id, name }) => ({ id, name })),
  };
}
export function documentUrl(patientId: string, id: string) {
  if (!numeric(patientId) || !numeric(id)) throw new Error("Invalid document.");
  return `${CHART_ORIGIN}/openemr/controller.php?document&retrieve&patient_id=${patientId}&document_id=${id}&as_file=true`;
}
