import { CHART_ORIGIN, numeric, type Result } from "./protocol.js";
const url = new URL(location.href);
if (
  location.origin === CHART_ORIGIN &&
  url.pathname === "/openemr/controller.php" &&
  url.searchParams.has("document") &&
  numeric(url.searchParams.get("patient_id"))
)
  mount();
function mount() {
  const patientId = url.searchParams.get("patient_id")!;
  const host = document.createElement("section");
  host.id = "chart-send-extension";
  host.setAttribute("aria-label", "Send fictional chart documents");
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `<style>:host{position:fixed;bottom:16px;right:16px;z-index:2147483647;width:330px;max-width:90vw;font:14px system-ui;color:#182d3b}section{padding:16px;border:1px solid #8ca5b3;border-radius:8px;background:#fff;box-shadow:0 4px 20px #0002}h2{font-size:17px;margin:0 0 8px}p{line-height:1.4}fieldset{max-height:180px;overflow:auto;border:0;padding:0;margin:10px 0}label{display:block;margin:6px 0;overflow-wrap:anywhere}button{background:#185a6f;color:#fff;border:0;border-radius:4px;padding:10px;cursor:pointer}button:disabled{opacity:.55;cursor:wait}small{display:block;margin-top:10px}</style><section><h2>Send chart documents</h2><p>Fictional local demo. Choose up to 10 files, then send once.</p><fieldset aria-label="Documents"></fieldset><button type="button">Send selected</button><p role="status" aria-live="polite">Choose documents from this chart.</p><small>Receiver address: extension options. Contents are never saved in extension storage.</small></section>`;
  document.body.append(host);
  const choices = root.querySelector("fieldset")!;
  const button = root.querySelector("button")!;
  const status = root.querySelector("[role=status]")!;
  let requestId = crypto.randomUUID();
  let busy = false;
  let retryable = false;
  const known = new Map<string, HTMLInputElement>();
  const scan = () => {
    for (const link of document.querySelectorAll<HTMLAnchorElement>(
      "a[href]",
    )) {
      let u: URL;
      try {
        u = new URL(link.href);
      } catch {
        continue;
      }
      const id = u.searchParams.get("doc_id");
      if (
        u.origin !== CHART_ORIGIN ||
        u.pathname !== "/openemr/controller.php" ||
        !u.searchParams.has("document") ||
        !u.searchParams.has("view") ||
        u.searchParams.get("patient_id") !== patientId ||
        !numeric(id) ||
        known.has(id)
      )
        continue;
      const name = (link.textContent?.trim() ?? "").slice(0, 200);
      if (!name) continue;
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = id;
      input.dataset.name = name;
      input.disabled = busy;
      input.addEventListener("change", () => {
        requestId = crypto.randomUUID();
        retryable = false;
        button.disabled = false;
        button.textContent = "Send selected";
        status.textContent = "Selection changed. Ready to send.";
      });
      label.append(input, document.createTextNode(` ${name}`));
      choices.append(label);
      known.set(id, input);
    }
  };
  scan();
  new MutationObserver(scan).observe(document.body, {
    subtree: true,
    childList: true,
  });
  button.addEventListener("click", async () => {
    if (busy) return;
    const documents = [...known.values()]
      .filter((i) => i.checked)
      .map((i) => ({ id: i.value, name: i.dataset.name! }));
    if (documents.length < 1 || documents.length > 10) {
      status.textContent = "Choose between 1 and 10 documents.";
      return;
    }
    busy = true;
    button.disabled = true;
    for (const input of known.values()) input.disabled = true;
    button.textContent = "Sending…";
    status.textContent = "Sending selected documents…";
    let result: Result;
    try {
      result = await chrome.runtime.sendMessage({
        type: "SEND",
        patientId,
        requestId,
        documents,
      });
      if (!result) throw new Error("No reply");
    } catch {
      result = {
        ok: false,
        retryable: true,
        error: "The extension disconnected. Reload the chart and try again.",
      };
    }
    busy = false;
    for (const input of known.values()) input.disabled = false;
    if (result.ok) {
      status.textContent = `Sent ${result.count} document${result.count === 1 ? "" : "s"}. Receipt: ${result.receipt}`;
      button.textContent = "Sent";
      button.disabled = true;
    } else {
      retryable = result.retryable;
      status.textContent = result.error;
      button.textContent = retryable
        ? "Retry send"
        : "Change selection to try again";
      button.disabled = !retryable;
    }
  });
}
