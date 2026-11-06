import { test } from "node:test";
import assert from "node:assert/strict";
import {
  receiverAddress,
  validateSend,
  documentUrl,
} from "../extension/protocol.js";
const chart =
  "http://127.0.0.1:8080/openemr/controller.php?document&patient_id=1";
const valid = {
  type: "SEND",
  patientId: "1",
  requestId: "00000000-0000-4000-8000-000000000001",
  documents: [{ id: "2", name: "fictional.txt" }],
};
test("accepts only the configured loopback receiver ports", () => {
  assert.equal(
    receiverAddress("http://127.0.0.1:4318/"),
    "http://127.0.0.1:4318",
  );
  for (const url of [
    "https://evil.test",
    "http://localhost:4318",
    "http://127.0.0.1:8080",
    "http://u:p@127.0.0.1:4318",
    "http://127.0.0.1:4318/path",
  ])
    assert.throws(() => receiverAddress(url));
});
test("rejects forged sender, wrong patient, invalid selection and arbitrary URLs", () => {
  assert.deepEqual(validateSend(valid, chart), valid);
  for (const url of [
    "https://evil.test/openemr/controller.php?document&patient_id=1",
    "http://127.0.0.1:8080/openemr/controller.php?document&patient_id=2",
    "http://127.0.0.1:8080/openemr/index.php?patient_id=1",
  ])
    assert.throws(() => validateSend(valid, url));
  for (const message of [
    { ...valid, documents: [] },
    { ...valid, documents: [{ id: "../secret", name: "x" }] },
    { ...valid, documents: Array(11).fill(valid.documents[0]) },
    { ...valid, documents: [valid.documents[0], valid.documents[0]] },
    { ...valid, requestId: "bad" },
    null,
  ])
    assert.throws(() => validateSend(message, chart));
  assert.equal(
    documentUrl("1", "2"),
    "http://127.0.0.1:8080/openemr/controller.php?document&retrieve&patient_id=1&document_id=2&as_file=true",
  );
});
