import { DEFAULT_RECEIVER, receiverAddress } from "./protocol.js";
const input = document.querySelector<HTMLInputElement>("#receiver")!;
const status = document.querySelector("[role=status]")!;
void chrome.storage.local
  .get("receiver")
  .then(({ receiver = DEFAULT_RECEIVER }) => {
    input.value = typeof receiver === "string" ? receiver : DEFAULT_RECEIVER;
  })
  .catch(() => {
    status.textContent = "Could not read settings. Reload this page.";
  });
document.querySelector("form")!.addEventListener("submit", (event) => {
  event.preventDefault();
  void (async () => {
    try {
      const receiver = receiverAddress(input.value.trim());
      await chrome.storage.local.set({ receiver });
      input.value = receiver;
      status.textContent = "Address saved.";
    } catch (error) {
      status.textContent =
        error instanceof Error ? error.message : "Could not save settings.";
    }
  })();
});
